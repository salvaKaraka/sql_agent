import os
from fastapi import FastAPI, HTTPException, Header, Depends
from sqlalchemy.exc import IntegrityError
import secrets

from db import init_admin_db, get_admin_session, get_tenant_db, get_schema_info, set_schema_info
from models import User, Tenant, TenantDatabase
from memory import add_message, get_context_window
from agent import init_sql_agent
from chains.clarificador import clarificador_chain
from chains.explicador import explicador_chain
from chains.clasificador import clasificador_chain
from chains.reformulador import reformulador_chain
from chains.corrector import corrector_chain

# Clave para proteger endpoints administrativos
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

app = FastAPI(on_startup=[init_admin_db])
#iniciar server con: uvicorn app:app --reload --host 0.0.0.0 --port 8000

# ----------------------------------------
# Dependencias de autenticación
# ----------------------------------------

def get_current_user(x_api_key: str = Header(...)):
    """
    Valida el header X-API-KEY y devuelve el usuario.
    """
    db = get_admin_session()
    user = db.query(User).filter_by(api_key=x_api_key).first()
    db.close()
    if not user:
        raise HTTPException(status_code=401, detail="API key inválida")
    return user


def get_admin(x_admin_key: str = Header(...)):
    """
    Valida el header X-ADMIN-KEY para endpoints administrativos.
    """
    if x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Admin API key inválida")
    return True

# ----------------------------------------
# Endpoints de administración
# ----------------------------------------

@app.post("/admin/register_tenant", dependencies=[Depends(get_admin)])
def register_tenant(name: str):
    """
    Registra un nuevo tenant (empresa).
    """
    db = get_admin_session()
    #verifica si ya existe el tenant, la id es autoincremental
    if db.query(Tenant).filter_by(name=name).first():
        db.close()
        raise HTTPException(400, "El tenant ya existe")
    if not name:
        db.close()
        raise HTTPException(400, "El nombre del tenant no puede estar vacío")
    if len(name) < 3:
        db.close()
        raise HTTPException(400, "El nombre del tenant debe tener al menos 3 caracteres")
    tenant = Tenant(name=name)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    db.close()
    return {"tenant_id": tenant.id, "name": tenant.name}

@app.post("/admin/register_database", dependencies=[Depends(get_admin)])
def register_database(tenant_id: int, base_name: str, db_path: str, schema_info: dict = {}):
    """
    Registra una nueva base de datos para un tenant existente.
    """
    db = get_admin_session()
    tenant = db.query(Tenant).get(tenant_id)
    if not tenant:
        db.close()
        raise HTTPException(404, "Tenant no encontrado")
    td = TenantDatabase(
        tenant_id=tenant.id,
        base_name=base_name,
        db_path=db_path,
        schema_info=schema_info
    )
    db.add(td)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        db.close()
        raise HTTPException(400, "Esta base ya está registrada para el tenant")
    db.refresh(td)
    db.close()
    return {"database_id": td.id, "base_name": td.base_name}

@app.post("/schema/{tenant_name}/{base_name}", dependencies=[Depends(get_admin)])
def modify_schema(
    tenant_name: str,
    base_name: str,
    payload: dict,
):
    """
    Example payload:
    {
        "schema": {
            "datos": "Descripción de la tabla de F1..."
        }
    }
    """
    # Validar payload
    new_schema = payload.get("schema")
    if new_schema is None:
        raise HTTPException(
            status_code=400, 
            detail="Falta el campo 'schema' en el body del request."
        )
    
    # Validar que el schema sea un diccionario
    if not isinstance(new_schema, dict):
        raise HTTPException(
            status_code=400,
            detail="El campo 'schema' debe ser un objeto JSON válido."
        )
    
    # Validar que el schema no esté vacío
    if not new_schema:
        raise HTTPException(
            status_code=400,
            detail="El esquema no puede estar vacío."
        )

    try:
        # Usar la función set_schema_info que maneja todo correctamente
        success = set_schema_info(tenant_name, base_name, new_schema)
        
        if success:
            # Opcional: obtener el formato que verá LangChain para confirmación
            langchain_format = get_schema_info(tenant_name, base_name)
            
            return {
                "status": "success",
                "message": "Esquema actualizado correctamente",
                "tenant": tenant_name,
                "database": base_name,
                "tables_updated": list(langchain_format.keys()) if langchain_format else [],
                "langchain_preview": {
                    table: desc[:100] + "..." if len(desc) > 100 else desc
                    for table, desc in langchain_format.items()
                } if langchain_format else {}
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Error interno al actualizar el esquema. Revisa los logs del servidor."
            )
            
    except ValueError as e:
        # Error de validación (tenant/database no encontrado)
        if "No se encontró" in str(e):
            if "tenant" in str(e).lower():
                raise HTTPException(status_code=404, detail=f"Tenant '{tenant_name}' no encontrado")
            else:
                raise HTTPException(status_code=404, detail=f"Base de datos '{base_name}' no encontrada para el tenant '{tenant_name}'")
        else:
            raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        # Error interno del servidor
        print(f"Error inesperado en modify_schema: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor al actualizar el esquema."
        )

@app.post("/admin/register_user", dependencies=[Depends(get_admin)])
def register_user(tenant_id: int, username: str):
    """
    Registra un nuevo usuario bajo un tenant dado y genera su api_key.
    """
    db = get_admin_session()
    tenant = db.query(Tenant).get(tenant_id)
    if not tenant:
        db.close()
        raise HTTPException(404, "Tenant no encontrado")
    if db.query(User).filter_by(username=username).first():
        db.close()
        raise HTTPException(400, "El usuario ya existe")
    api_key = secrets.token_urlsafe(32)
    user = User(username=username, api_key=api_key, tenant_id=tenant.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return {"user_id": user.id, "username": user.username, "api_key": user.api_key}

# ----------------------------------------
# Endpoints de usuario
# ----------------------------------------

@app.post("/query/{tenant_name}/{base_name}")
def query_sql(
    tenant_name: str,
    base_name: str,
    payload: dict,
    user: User = Depends(get_current_user)
):
    """
    Procesa una consulta SQL en lenguaje natural usando contexto persistente.
    """
    # 1) Obtener pregunta del usuario
    pregunta = payload.get("question")
    if not pregunta:
        raise HTTPException(status_code=400, detail="Falta campo 'question'")

    # 2) Guardar pregunta original en la conversación
    add_message(tenant_name, user.id, "user", pregunta)

    # 3) Cargar contexto de conversación previa
    context = get_context_window(tenant_name, user.id)
    context_text = "\n".join(f"{r}: {c}" for r, c in context) if context else ""

    # 4) Cargar esquema semántico de la base
    schema_dict = get_schema_info(tenant_name, base_name)
    schema_text = str(schema_dict) if schema_dict else ""

    # 5) Proceso de clarificación
    clar = clarificador_chain.run({
        "schema": schema_text,
        "contexto": context_text,
        "pregunta": pregunta
    }).strip()

    add_message(tenant_name, user.id, "assistant_clarification", clar)

    if clar != "NO_CLARIFICATION_NEEDED":
        return {
            "status": "clarification",
            "questions": clar.split("\n")
        }

    # 6) Ejecutar la consulta con el agente SQL
    try:
        SessionDB = get_tenant_db(tenant_name, base_name)
        db_path = SessionDB().bind.url.database

        # 🧠 Armar input final para el agente SQL
        input_text = f"""Cuando tengas la respuesta final, respondé con:

Final Answer: [tu respuesta]

No agregues ningún otro texto fuera de ese formato.

        Contexto previo:
{context_text}

Esquema de la base:
{schema_text}

Pregunta del usuario:
{pregunta}

Aclaraciones:
{clar}
"""

        # 🎯 Ejecutar agente
        sql_agent = init_sql_agent(
            db_path=db_path,
            tenant_name=tenant_name,
            base_name=base_name
        )
        resultado = sql_agent.run({"input": input_text})

    except Exception as e:
            error_msg = str(e)

            # Llamás a la chain de corrección
            fixed_query = corrector_chain.run({
                "schema": schema_text,
                "query": input_text,
                "error": error_msg,
            })
            resultado = sql_agent.run(fixed_query.strip())

    # 7) Generar explicación del resultado
    explic = explicador_chain.run({
        "contexto": context_text,
        "pregunta": pregunta,
        "schema": schema_text,
        "resultado": resultado

    }).strip()

    # 8) Guardar resultado y explicación en la conversación
    add_message(tenant_name, user.id, "assistant_query_result", resultado)
    add_message(tenant_name, user.id, "assistant_explanation", explic)

    return {
        "status": "success",
        "result": resultado,
        "explicacion": explic
    }

@app.post("/feedback/{tenant_name}/{base_name}")
def feedback(
    tenant_name: str,
    base_name: str,
    payload: dict,
    user: User = Depends(get_current_user)
):
    """
    Recibe feedback del usuario y, si no fue útil, reformula la consulta.
    """
    fb = payload.get("feedback", "")
    if not fb:
        raise HTTPException(400, "Falta campo 'feedback'")

    utilidad = clasificador_chain.run({"feedback": fb}).strip().lower()
    add_message(tenant_name, user.id, "user_feedback", fb)

    if utilidad == "útil":
        return {"status": "ok", "message": "¡Genial que haya servido!"}

    context = get_context_window(tenant_name, user.id)
    hist_str = "\n".join(f"{r}: {c}" for r, c in context)
    nueva = reformulador_chain.run({"historial": hist_str, "nueva_aclaracion": fb}).strip()

    add_message(tenant_name, user.id, "assistant_reformulated_query", nueva)
    return {"status": "reformulate", "new_query": nueva}
