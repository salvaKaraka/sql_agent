from sqlalchemy import create_engine
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain.agents import AgentType
from config import LLM_MODEL, GOOGLE_API_KEY
from db import get_schema_info

def init_llm():
    return ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        temperature=0,
        google_api_key=GOOGLE_API_KEY,
    )

def init_sql_agent(db_path: str, tenant_name: str, base_name: str):
    llm = init_llm()
    # Carga descripciones semánticas
    info = get_schema_info(tenant_name, base_name)
    # crea agente con custom_table_info
    db = SQLDatabase(
        engine=create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False}),
        custom_table_info=info
    )
    return create_sql_agent(
        llm=llm,
        db=db,
        agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
        handle_parsing_errors=True
    )
