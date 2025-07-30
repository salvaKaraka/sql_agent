
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from agent import init_llm

explain_prompt = PromptTemplate.from_template("""
Tenés que explicarle al usuario un resultado de una consulta SQL que pidió en lenguaje natural, abstrayendolo por completo de la base de datos.
Asume que el usuario no tiene conocimientos técnicos de SQL o bases de datos, ni le interesa, solo quiere entender el resultado de su consulta.

contexto:
{contexto}
                                                                                    
Pregunta original:
"{pregunta}"

Esquema de la base de datos:
{schema}
                                                                        
Resultado de la consulta SQL:
"{resultado}"

Explicá en lenguaje claro, conciso y sin jerga técnica, qué significan estos datos para un usuario sin conocimientos técnicos. No lo hagas muy largo y con vueltas, solo lo necesario para que el usuario entienda el resultado de su consulta.
Finaliza con una pregunta o frase que busque el feedback del usuario sobre la utilidad de la explicación, como "¿Te resultó útil esta explicación?" o "¿Quedaste satisfecho con la respuesta?".
""")

explicador_chain = LLMChain(llm=init_llm(), prompt=explain_prompt)
