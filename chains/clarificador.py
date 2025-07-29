from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from agent import init_llm

clarify_prompt = PromptTemplate(
    input_variables=["schema", "pregunta"],
    template="""Sos un experto en bases de datos SQL y entendés el esquema semántico de la base de datos.
La base de datos tiene este esquema semántico:
{schema}

Un usuario te va a hacer una consulta en lenguaje natural. Tu tarea es identificar si la consulta es ambigua o falta información:
- Si la consulta original es ambigua o puede interpretarse de más de una forma, hacé preguntas aclaratorias.
- Si la consulta es clara y no necesita aclaración, devolvé exactamente: NO_CLARIFICATION_NEEDED

Ejemplo:
Usuario: ¿Cuántos atendió Juan?
Asistente:
1. ¿A qué se refiere con "atendió"? (consultas, estudios, turnos, etc.)
2. ¿Quién es "Juan"? ¿Tenés apellido o rol (médico, paciente)?
3. ¿Querés filtrar por fechas?

Ejemplo de pregunta clara:
Usuario: ¿Cuántos pacientes atendió Juan Pérez en 2023?
Asistente: NO_CLARIFICATION_NEEDED

Generá preguntas cortas y claras para que el usuario aclare su intención, una por línea. No respondas la consulta.

Usuario: "{pregunta}"

¿Hay algo ambiguo o faltan detalles? Si es necesario, formulá preguntas cortas para aclarar. Si no, devolvé EXACTAMENTE: NO_CLARIFICATION_NEEDED
"""
)

clarificador_chain = LLMChain(llm=init_llm(), prompt=clarify_prompt)
