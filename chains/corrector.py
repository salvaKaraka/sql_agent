from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from agent import init_llm

correct_prompt = PromptTemplate.from_template("""
La siguiente consulta SQL produjo un error al ejecutarse:
Esquema: {schema}
Query: {query}
Error: {error}

Corrige la consulta para que sea válida según el esquema y devuélvela (solo la SQL).
""")

corrector_chain = LLMChain(llm=init_llm(), prompt=correct_prompt)
