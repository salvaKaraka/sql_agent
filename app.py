import os
from fastapi import FastAPI, HTTPException, Header, Depends
from sqlalchemy.exc import IntegrityError
import secrets

from db import init_admin_db, get_admin_session, get_tenant_db, get_schema_info
from models import User, Tenant, TenantDatabase
from memory import add_message, get_context_window
from agent import init_sql_agent
from chains.clarificador import clarificador_chain
from chains.explicador import explicador_chain
from chains.clasificador import clasificador_chain
from chains.reformulador import reformulador_chain
from chains.corrector import corrector_chain

# Clave para proteger endpoints administrativos
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "cambia_esta_clave_segura")

app = FastAPI(on_startup=[init_admin_db])

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
    if db.query(Tenant).filter_by(name=name).first():
        db.close()
        raise HTTPException(400, "El tenant ya existe")
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
    pregunta = payload.get("question")
    if not pregunta:
        raise HTTPException(400, "Falta campo 'question'")

    # 1) Guardar pregunta del usuario
    add_message(tenant_name, user.id, "user", pregunta)

    # 2) Cargar contexto previo
    context = get_context_window(tenant_name, user.id)
    context_text = "\n".join(f"{r}: {c}" for r, c in context)

    # 3) Obtener esquema de la base
    schema_dict = get_schema_info(tenant_name, base_name)
    schema_text = "\n".join(f"{t}: {d}" for t, d in schema_dict.items())

    # 4) Clarificación
    clar = clarificador_chain.run({
        "context": context_text,
        "schema": schema_text,
        "pregunta": pregunta
    }).strip()
    add_message(tenant_name, user.id, "assistant_clarification", clar)
    if clar != "NO_CLARIFICATION_NEEDED":
        return {"status": "clarification", "questions": clar.split("\n")}  

    # 5) Ejecutar la consulta
    try:
        SessionDB = get_tenant_db(tenant_name, base_name)
        db_path = SessionDB().bind.url.database
        resultado, explic = init_sql_agent(
            sqlite_uri=f"sqlite:///{db_path}",
            chains={"corrector": corrector_chain, "explicador": explicador_chain}
        ).run({
            "context": context_text,
            "pregunta": pregunta,
            "aclaraciones": clar
        })
    except Exception as e:
        raise HTTPException(500, f"Error al ejecutar SQL: {e}")

    # 6) Guardar resultado y explicación
    add_message(tenant_name, user.id, "assistant_query_result", resultado)
    add_message(tenant_name, user.id, "assistant_explanation", explic)

    return {"status": "success", "result": resultado, "explicacion": explic}

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
