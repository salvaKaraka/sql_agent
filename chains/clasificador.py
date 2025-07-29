from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from agent import init_llm

classify_prompt = PromptTemplate.from_template("""
Sos un asistente que clasifica si una explicación fue útil para el usuario.


tras recibir la explicación, esta fue la respuesta del usuario:
"{feedback}"

si el usuario considera que la explicación lo dejo satisfecho y sin dudas, esta fue útil, sino no.
Clasificá esta respuesta como una de las siguientes opciones (solo una palabra):
- útil
- no útil 
""")

clasificador_chain = LLMChain(llm=init_llm(), prompt=classify_prompt)
