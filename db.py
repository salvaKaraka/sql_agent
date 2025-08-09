import json
import os
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config import ADMIN_DB_URL
from models import Base, Tenant, TenantDatabase, ChatMessage, SemanticCache
from openai import OpenAI
from typing import Dict, Any

# Engine y sesión para la base de administración
admin_engine = create_engine(ADMIN_DB_URL)
AdminSession = sessionmaker(bind=admin_engine)

def init_admin_db():
    """Crea/abre las tablas admin."""
    Base.metadata.create_all(admin_engine)

def get_admin_session():
    """Devuelve una nueva sesión a tenants.db"""
    return AdminSession()

# -------------------------------
#  Funciones para esquema
# -------------------------------

def get_schema_info(tenant_name: str, base_name: str) -> Dict[str, str]:
    """
    Get schema info and convert it to the format expected by LangChain.
    Returns a dict where keys are table names and values are descriptive strings.
    """
    db = get_admin_session()

    result = (
        db.query(TenantDatabase)
        .join(Tenant)
        .filter(Tenant.name == tenant_name, TenantDatabase.base_name == base_name)
        .first()
    )

    db.close()

    if not result:
        raise Exception(f"No se encontró la base {base_name} para el tenant {tenant_name}")

    if not result.schema_info:
        return {}

    try:
        # Parse the JSON string stored in schema_info
        if isinstance(result.schema_info, str):
            schema_data = json.loads(result.schema_info)
        else:
            schema_data = result.schema_info
        
        # Convert to LangChain format (table_name -> description_string)
        langchain_format = {}
        
        for table_name, table_info in schema_data.items():
            if isinstance(table_info, str):
                # Already a simple string description
                langchain_format[table_name] = table_info
            elif isinstance(table_info, dict):
                # Convert detailed format to string
                description_parts = []
                
                # Add main description
                if 'description' in table_info:
                    description_parts.append(f"Tabla: {table_name}")
                    description_parts.append(f"Descripción: {table_info['description']}")
                
                # Add column information
                if 'columns' in table_info:
                    description_parts.append("\nColumnas:")
                    columns = table_info['columns']
                    if isinstance(columns, dict):
                        for col_name, col_desc in columns.items():
                            if isinstance(col_desc, str):
                                description_parts.append(f"- {col_name}: {col_desc}")
                            elif isinstance(col_desc, dict):
                                col_description = col_desc.get('description', 'Sin descripción')
                                col_type = col_desc.get('type', '')
                                type_info = f" ({col_type})" if col_type else ""
                                description_parts.append(f"- {col_name}{type_info}: {col_description}")
                
                # Add business rules if present
                if 'business_rules' in table_info:
                    description_parts.append(f"\nReglas de negocio: {table_info['business_rules']}")
                
                # Add relationships if present
                if 'relationships' in table_info:
                    description_parts.append(f"Relaciones: {table_info['relationships']}")
                
                langchain_format[table_name] = "\n".join(description_parts)
            else:
                # Fallback for other types
                langchain_format[table_name] = str(table_info)
        
        return langchain_format
        
    except json.JSONDecodeError as e:
        print(f"Error parsing schema JSON: {e}")
        return {}
    except Exception as e:
        print(f"Error processing schema: {e}")
        return {}

def set_schema_info(tenant_name: str, base_name: str, schema_info: Dict[str, Any]) -> bool:
    """
    Set schema info for a tenant database.
    
    Args:
        tenant_name: Name of the tenant
        base_name: Name of the database
        schema_info: Schema information dictionary
    
    Returns:
        bool: True if successful, False otherwise
    """
    db = get_admin_session()
    
    try:
        result = (
            db.query(TenantDatabase)
            .join(Tenant)
            .filter(Tenant.name == tenant_name, TenantDatabase.base_name == base_name)
            .first()
        )
        
        if not result:
            raise Exception(f"No se encontró la base {base_name} para el tenant {tenant_name}")
        
        # Convert to JSON string for storage
        result.schema_info = json.dumps(schema_info, ensure_ascii=False, indent=2)
        db.commit()
        return True
        
    except Exception as e:
        db.rollback()
        print(f"Error setting schema info: {e}")
        return False
    finally:
        db.close()

# -------------------------------
#  Funciones para DB del tenant
# -------------------------------

def get_tenant_db(tenant_name: str, base_name: str):
    db = get_admin_session()
    tenant = db.query(Tenant).filter_by(name=tenant_name).first()
    if not tenant:
        db.close()
        raise ValueError(f"Tenant {tenant_name} no encontrado")

    td = db.query(TenantDatabase).filter_by(tenant_id=tenant.id, base_name=base_name).first()
    db.close()
    if not td:
        raise ValueError(f"Base {base_name} no encontrada para tenant {tenant_name}")

    db_path = td.db_path.strip()

    # Si es SQLite y no tiene prefijo, lo agregamos
    if db_path.endswith(".db") and not db_path.startswith("sqlite"):
        db_path = f"sqlite:///{db_path}"

    print(f"[DEBUG] db_path normalizado: {db_path}")

    tenant_engine = create_engine(
        db_path,
        connect_args={"check_same_thread": False} if db_path.startswith("sqlite") else {}
    )
    TenantSession = sessionmaker(bind=tenant_engine)
    return TenantSession


# -------------------------------
#  Cache semántico persistente
# -------------------------------

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def embed_text(texto: str) -> list[float]:
    """Genera el embedding de un texto usando OpenAI."""
    resp = client.embeddings.create(
        model="text-embedding-ada-002",
        input=texto
    )
    return resp.data[0].embedding  # lista de floats

def get_semantic_cached_query(tenant_name: str, user_id: int, pregunta: str, threshold: float = 0.85):
    """Busca en la cache semántica la respuesta más similar a la pregunta dada."""
    db = get_admin_session()
    tenant = db.query(Tenant).filter_by(name=tenant_name).first()
    if not tenant:
        db.close()
        return None

    pregunta_embedding = np.array(embed_text(pregunta), dtype=np.float32)

    results = (
        db.query(SemanticCache.question, SemanticCache.embedding, SemanticCache.answer)
          .filter_by(tenant_id=tenant.id, user_id=user_id)
          .all()
    )
    db.close()

    best_match = None
    best_score = -1

    for question_guardada, embedding_guardada, respuesta in results:
        embedding_guardada = np.array(embedding_guardada, dtype=np.float32)

        sim = np.dot(pregunta_embedding, embedding_guardada) / (
            np.linalg.norm(pregunta_embedding) * np.linalg.norm(embedding_guardada)
        )

        if sim > best_score:
            best_score = sim
            best_match = respuesta

    if best_score >= threshold:
        return best_match

    return None


def set_semantic_cached_query(tenant_name: str, user_id: int, pregunta: str, answer: str):
    """Guarda en cache semántico persistente."""
    db = get_admin_session()
    tenant = db.query(Tenant).filter_by(name=tenant_name).first()
    if not tenant:
        db.close()
        return

    pregunta_embedding = embed_text(pregunta)

    cache_entry = SemanticCache(
        tenant_id=tenant.id,
        user_id=user_id,
        question=pregunta,
        embedding=pregunta_embedding,  # lista de floats
        answer=answer
    )
    db.add(cache_entry)
    db.commit()
    db.close()
