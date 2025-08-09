import os
from sqlalchemy import create_engine
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain.agents import AgentType
from config import LLM_MODEL, MODEL_API_KEY
from db import get_schema_info
from langchain.agents.agent_toolkits import SQLDatabaseToolkit
from langchain.globals import set_llm_cache
from langchain.cache import SQLiteCache

# Configuración global de cache LLM (persistente en SQLite local)
set_llm_cache(SQLiteCache(database_path="./data/llm_cache.db"))

# Cache en memoria para instancias de agentes SQL
AGENT_CACHE = {}

def init_llm():
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=0,
        api_key=MODEL_API_KEY,
    )

def init_sql_agent(db_path: str, tenant_name: str, base_name: str):
    """
    Devuelve un agente SQL para el tenant/base indicados.
    Usa cache en memoria para no recrear el agente en cada request.
    """
    cache_key = f"{tenant_name}:{base_name}"
    if cache_key in AGENT_CACHE:
        return AGENT_CACHE[cache_key]

    llm = init_llm()
    info = get_schema_info(tenant_name, base_name)

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"No se encontró la base de datos en: {db_path}")

    if not db_path.startswith("sqlite") and not db_path.startswith("postgresql"):
        db_path = f"sqlite:///{db_path}"
    db = SQLDatabase(
        engine=create_engine(db_path, connect_args={"check_same_thread": False} if db_path.startswith("sqlite") else {}),
        custom_table_info=info
    )

    toolkit = SQLDatabaseToolkit(db=db, llm=llm)

    agent = create_sql_agent(
        llm=llm,
        toolkit=toolkit,
        agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=False,
        handle_parsing_errors=True
    )

    AGENT_CACHE[cache_key] = agent
    return agent
