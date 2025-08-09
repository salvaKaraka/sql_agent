import secrets
from fastapi import FastAPI, HTTPException, Header, Depends
from sqlalchemy.exc import IntegrityError
from config import ADMIN_API_KEY
from db import (
    init_admin_db, get_admin_session, get_tenant_db,
    get_schema_info, set_schema_info,
    get_semantic_cached_query, set_semantic_cached_query
)
from models import User, Tenant, TenantDatabase
from memory import add_message, get_context_window
from agent import init_sql_agent

# Cache LLM local
from langchain.globals import set_llm_cache
from langchain.cache import SQLiteCache
set_llm_cache(SQLiteCache(database_path="./data/llm_cache.db"))


app = FastAPI(on_startup=[init_admin_db])

# ---------------------------
# Autenticación
# ---------------------------

def get_current_user(x_api_key: str = Header(...)):
    db = get_admin_session()
    user = db.query(User).filter_by(api_key=x_api_key).first()
    db.close()
    if not user:
        raise HTTPException(status_code=401, detail="API key inválida")
    return user

def get_admin(x_admin_key: str = Header(...)):
    if x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Admin API key inválida")
    return True

# ---------------------------
# Endpoints admin
# ---------------------------

@app.post("/admin/register_tenant", dependencies=[Depends(get_admin)])
def register_tenant(name: str):
    db = get_admin_session()
    if db.query(Tenant).filter_by(name=name).first():
        db.close()
        raise HTTPException(400, "El tenant ya existe")
    if not name or len(name) < 3:
        db.close()
        raise HTTPException(400, "Nombre inválido")
    tenant = Tenant(name=name)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    db.close()
    return {"tenant_id": tenant.id, "name": tenant.name}

@app.post("/admin/register_database", dependencies=[Depends(get_admin)])
def register_database(tenant_id: int, base_name: str, db_path: str, schema_info: dict = {}):
    db = get_admin_session()
    tenant = db.query(Tenant).get(tenant_id)
    if not tenant:
        db.close()
        raise HTTPException(404, "Tenant no encontrado")
    td = TenantDatabase(
        tenant_id=tenant.id, base_name=base_name,
        db_path=db_path, schema_info=schema_info
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
def modify_schema(tenant_name: str, base_name: str, payload: dict):
    new_schema = payload.get("schema")
    if not isinstance(new_schema, dict) or not new_schema:
        raise HTTPException(status_code=400, detail="Esquema inválido")
    set_schema_info(tenant_name, base_name, new_schema)
    return {"status": "success", "message": "Esquema actualizado"}

@app.post("/admin/register_user", dependencies=[Depends(get_admin)])
def register_user(tenant_id: int, username: str):
    db = get_admin_session()
    tenant = db.query(Tenant).get(tenant_id)
    if not tenant:
        db.close()
        raise HTTPException(404, "Tenant no encontrado")
    if db.query(User).filter_by(username=username).first():
        db.close()
        raise HTTPException(400, "Usuario ya existe")
    api_key = secrets.token_urlsafe(32)
    user = User(username=username, api_key=api_key, tenant_id=tenant.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return {"user_id": user.id, "username": user.username, "api_key": user.api_key}

# ---------------------------
# Endpoint de usuario
# ---------------------------

@app.post("/query/{tenant_name}/{base_name}")
def query_sql(tenant_name: str, base_name: str, payload: dict, user: User = Depends(get_current_user)):
    pregunta = payload.get("question")
    if not pregunta:
        raise HTTPException(status_code=400, detail="Falta campo 'question'")

    add_message(tenant_name, user.id, "user", pregunta)
    context = get_context_window(tenant_name, user.id)
    context_text = "\n".join(f"{r}: {c}" for r, c in context) if context else ""
    schema_dict = get_schema_info(tenant_name, base_name)
    schema_text = str(schema_dict) if schema_dict else ""

    # 1️⃣ Cache semántico persistente
    cached_result = get_semantic_cached_query(tenant_name, user.id, pregunta)
    if cached_result:
        add_message(
        tenant_name, user.id, "assistant_query_result", cached_result,
        tokens_prompt=0, tokens_completion=0, used_cache=True
        )
        return {"status": "success", "result": cached_result, "explicacion": "Respuesta desde cache semántico"}

    # 2️⃣ Ejecutar consulta
    try:
        SessionDB = get_tenant_db(tenant_name, base_name)
        db_path = SessionDB().bind.url.database
        input_text = f"""
Sos un experto en SQL.
Contexto:
{context_text}

Esquema:
{schema_text}

Pregunta:
{pregunta}

Instrucciones:
- Si falta información, devolvé solo las preguntas necesarias (una por línea).
- Si la consulta es clara, generá el SQL, ejecutalo y devolvé:
Final Answer: [respuesta]
"""
        sql_agent = init_sql_agent(db_path=db_path, tenant_name=tenant_name, base_name=base_name)
        resultado = sql_agent.run({"input": input_text})
        # Si el agente devuelve metadata de tokens
        token_usage = resultado.get("token_usage", {}) if isinstance(resultado, dict) else {}
        prompt_tokens = token_usage.get("prompt_tokens", None)
        completion_tokens = token_usage.get("completion_tokens", None)

        add_message(
            tenant_name, user.id, "assistant_query_result", resultado if isinstance(resultado, str) else resultado.get("output", ""),
            tokens_prompt=prompt_tokens, tokens_completion=completion_tokens, used_cache=False
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando consulta: {str(e)}")

    # 3️⃣ Guardar respuesta
    add_message(tenant_name, user.id, "assistant_query_result", resultado)
    set_semantic_cached_query(tenant_name, user.id, pregunta, resultado)

    return {"status": "success", "result": resultado, "explicacion": "Consulta ejecutada"}
