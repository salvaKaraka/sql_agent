# db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Tenant, TenantDatabase
from config import ADMIN_DB_URL
import json
from typing import Dict, Any

# Engine y sesión para la base de administración (tenants.db)
admin_engine = create_engine(ADMIN_DB_URL, connect_args={"check_same_thread": False})
AdminSession = sessionmaker(bind=admin_engine)

def init_admin_db():
    """Crea/abre las tablas admin: tenants + tenant_databases"""
    Base.metadata.create_all(admin_engine)

def get_admin_session():
    """Devuelve una nueva sesión a tenants.db"""
    return AdminSession()

def get_tenant_db(tenant_name: str, base_name: str):
    db = AdminSession()
    
    entry = (
        db.query(TenantDatabase)
          .join(Tenant)
          .filter(Tenant.name == tenant_name, TenantDatabase.base_name == base_name)
          .first()
    )
    
    db.close()
    if not entry:
        raise ValueError(f"No se encontró base '{base_name}' para tenant '{tenant_name}'")
    
    path = entry.db_path
    engine_t = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    return sessionmaker(bind=engine_t)


def create_tenant(name: str):
    db = AdminSession()
    tenant = Tenant(name=name)
    db.add(tenant)
    db.commit()
    db.close()

def register_tenant_database(tenant_name: str, base_name: str, db_path: str, schema_info: dict):
    print("Registrando nueva base...")
    
    if not db_path.startswith("sqlite:///"):
        if not db_path.startswith("./"):
            db_path = f"./{db_path}"

    db = AdminSession()

    tenant = db.query(Tenant).filter_by(name=tenant_name).first()
    if not tenant:
        tenant = Tenant(name=tenant_name)
        db.add(tenant)
        db.commit()

    existing = db.query(TenantDatabase).filter_by(tenant_id=tenant.id, base_name=base_name).first()

    if existing:
        print("Ya existe, actualizando...")
        existing.db_path = db_path
        existing.schema_info = schema_info
    else:
        print("No existe, creando...")
        new_entry = TenantDatabase(
            tenant_id=tenant.id,
            base_name=base_name,
            db_path=db_path,
            schema_info=schema_info
        )
        db.add(new_entry)

    db.commit()
    db.close()
    print("Registro completado.")


def list_tenant_databases(tenant_name: str):
    db = AdminSession()
    tenant = db.query(Tenant).filter_by(name=tenant_name).first()
    if not tenant:
        db.close()
        return []

    bases = (
        db.query(TenantDatabase)
        .filter_by(tenant_id=tenant.id)
        .all()
    )
    db.close()
    return [(b.base_name, b.db_path) for b in bases]

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