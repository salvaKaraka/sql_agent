from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from agent import init_llm

reformulate_prompt = PromptTemplate.from_template("""
Tenés una conversación previa con el usuario, en la que se intentó responder una pregunta en lenguaje natural transformándola en SQL. A continuación se incluye el historial y un comentario final del usuario.

Historial de interacción:
{historial}

Usuario aclaró o corrigió:
"{nueva_aclaracion}"

Reformulá una nueva pregunta clara, específica y completa en lenguaje natural que tenga en cuenta todo el contexto y la aclaración.
Solo devolvé la nueva pregunta, sin explicaciones adicionales.
""")

reformulador_chain = LLMChain(llm=init_llm(), prompt=reformulate_prompt)
