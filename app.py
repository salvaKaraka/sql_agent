from fastapi import FastAPI, HTTPException
from uuid import uuid4
from db import init_admin_db, get_tenant_db, get_schema_info
from memory import add_message, load_memory
from agent import init_sql_agent
from models import Tenant, TenantDatabase
from chains.clarificador import clarificador_chain
from chains.explicador import explicador_chain
from chains.clasificador import clasificador_chain
from chains.reformulador import reformulador_chain
from chains.corrector import corrector_chain

app = FastAPI(on_startup=[init_admin_db])

@app.post("/start_session/{tenant_name}/{base_name}")
def start_session(tenant_name: str, base_name: str):
    """
    Inicia una nueva sesión y devuelve un session_id.
    """
    # falta: validar que tenant y base existan
    session_id = str(uuid4())
    return {"session_id": session_id}

@app.post("/query/{tenant_name}/{base_name}/{session_id}")
def query_sql(tenant_name: str, base_name: str, session_id: str, payload: dict):
    pregunta = payload.get("question")
    if not pregunta:
        raise HTTPException(400, "Falta campo 'question'")

    # 1) Schema semántico
    schema = get_schema_info(tenant_name, base_name)
    schema_text = "\n".join(f"{t}: {d}" for t,d in schema.items())

    # 2) Clarificación
    clar = clarificador_chain.run({
        "schema": schema_text,
        "pregunta": pregunta
    }).strip()
    if clar != "NO_CLARIFICATION_NEEDED":
        return {"status":"clarification", "questions": clar.split("\n")}

    # 3) Ejecutar / corregir SQL
    try:
        SessionDB = get_tenant_db(tenant_name, base_name)
        db_path = SessionDB().bind.url.database
        agent = init_sql_agent(db_path, tenant_name, base_name)
        resultado = agent.run(pregunta)
    except Exception as e:
        fixed = corrector_chain.run({"query": pregunta, "error": str(e)})
        resultado = agent.run(fixed)

    # 4) Explicación
    explic = explicador_chain.run({
        "pregunta": pregunta,
        "aclaraciones": clar if clar!="NO_CLARIFICATION_NEEDED" else "",
        "resultado": resultado
    })

    # 5) Guardar memoria
    add_message(tenant_name, session_id, "user", pregunta)
    add_message(tenant_name, session_id, "assistant", resultado)

    return {
        "status": "success",
        "result": resultado,
        "explicacion": explic
    }

@app.post("/feedback/{tenant_name}/{base_name}/{session_id}")
def feedback(tenant_name: str, base_name: str, session_id: str, payload: dict):
    """
    Recibe feedback del usuario. Si es 'no útil', reformula la consulta.
    """
    fb = payload.get("feedback","")
    if not fb:
        raise HTTPException(400, "Falta campo 'feedback'")
    utilidad = clasificador_chain.run({"feedback": fb}).strip().lower()
    if utilidad == "útil":
        return {"status":"ok", "message":"¡Genial que haya servido!"}
    # Si no fue útil → reformular
    historial = load_memory(tenant_name, session_id)
    # construir string de historial
    hist_str = "\n".join(f"{r}: {c}" for r,c in historial)
    nueva = reformulador_chain.run({
        "historial": hist_str,
        "nueva_aclaracion": fb
    }).strip()
    return {"status":"reformulate", "new_query": nueva}
