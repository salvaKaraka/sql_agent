# 📘 Documentación del Proyecto: SQL Agent

El proyecto **SQL Agent** es una aplicación construida sobre **FastAPI** y **LangChain** que traduce consultas en lenguaje natural a sentencias SQL, ejecuta dichas consultas en bases de datos SQLite y devuelve los resultados al usuario. Incluye:

* Gestión de múltiples *tenants* y bases de datos.
* Memoria para almacenar y recuperar el contexto de conversaciones.
* Modularidad mediante cadenas de razonamiento (clarificación, corrección, clasificación, explicación y reformulación).
* API RESTful para integración con otros sistemas.

---

## 🔌 Endpoints Disponibles

A continuación, se describen en orden los endpoints REST que expone el servidor:

| Operación             | Método | Ruta                                                | Descripción                                                                                                      |
| --------------------- | ------ | --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Agregar *tenant*      | POST   | `/tenant`                                           | Crea un nuevo tenant. Payload: `{ "name": "<tenant_name>" }`.                                                    |
| Agregar base de datos | POST   | `/tenant/{tenant_name}/database`                    | Registra una base de datos para el tenant. Payload: `{ "base_name": "<base_name>", `schema\_info`: {...} }`.     |
| Agregar usuario       | POST   | `/tenant/{tenant_name}/database/{base_name}/user`   | Crea un usuario asociado a esa base. Payload: `{ "user": "<username>", "permissions": [...] }`.                  |
| Realizar consulta     | POST   | `/query/{tenant_name}/{base_name}`                  | Traduce la consulta en lenguaje natural a SQL y ejecuta. Payload: `{ "query": "<NL_query>", "history": [...] }`. |
| Modificar esquema     | PUT    | `/tenant/{tenant_name}/database/{base_name}/schema` | Sobrescribe el esquema de la base. Payload: `{ "schema_info": {...} }`.                                          |

---

## 📦 Requisitos

* Python 3.10 o superior.
* Dependencias listadas en `requirements.txt`.

---

## ⚙️ Instalación

```bash
# Clonar el repositorio
git clone <URL_DEL_REPOSITORIO>
cd sql_agent

# Crear entorno virtual
env="venv" && python3 -m venv $env
source $env/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

> 💡 Asegúrate de crear un archivo `.env` con tus variables de entorno.

---

## 🗂️ Estructura del Proyecto

```text
sql_agent/
├── app.py               # Servidor FastAPI
├── agent.py             # Lógica principal del agente de LangChain
├── config.py            # Configuración de entorno y llaves
├── db.py                # Inicialización de motor SQLAlchemy
├── models.py            # Definición de modelos ORM
├── memory.py            # Infraestructura de memoria de conversaciones
├── chains/              # Cadenas de razonamiento
│   ├── clarificador.py
│   ├── corrector.py
│   ├── clasificador.py
│   ├── explicador.py
│   └── reformulador.py
├── borrar_todo.py       # Script de limpieza de datos (testing)
├── tempCodeRunnerFile.py# Código de pruebas temporales
├── data/                # Datos de ejemplo y bases SQLite
│   ├── f1.db
│   ├── f1_schema.json
│   └── tenants.db       # Base de datos del servidor
└── requirements.txt     # Dependencias del proyecto
```

---

## 🔧 Configuración

En `config.py` se cargan variables de entorno y llaves necesarias:

```python
from dotenv import load_dotenv
import os

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ADMIN_DB_URL = os.getenv("ADMIN_DB_URL", "sqlite:///./data/tenants.db")
```

Asegúrate de definir `GOOGLE_API_KEY` en un archivo `.env` en la raíz del proyecto.

---

## 🔁 Cadenas de Razonamiento (*Chains*)

Dentro de `chains/` se encuentran varios módulos, cada uno implementa una cadena específica para el procesamiento del lenguaje natural:

* **clarificador.py**: solicita aclaraciones si la consulta es ambigua.
* **corrector.py**: corrige la sintaxis de la sentencia SQL generada.
* **clasificador.py**: clasifica el tipo de consulta (SELECT, INSERT, etc.).
* **explicador.py**: explica los resultados devueltos por la consulta.
* **reformulador.py**: mejora la consulta basándose en retroalimentación.

Cada módulo define una función `get_chain(...)` que devuelve una instancia de `Chain` configurada con prompts y llaves necesarias.

---

## 🧠 Agente Principal (`agent.py`)

Este archivo contiene la clase `SQLAgent`, la cual se encarga de orquestar las cadenas, gestionar la memoria y ejecutar las consultas SQL:

```python
class SQLAgent:
    def __init__(self, session, tenant_name, base_name):
        # Cargar esquema JSON desde DB o archivo
        # Inicializar memoria y cadenas

    def run(self, user_input: str) -> dict:
        # 1. Clarificar
        # 2. Generar SQL
        # 3. Corregir SQL
        # 4. Ejecutar en SQLite
        # 5. Explicar resultados
        # 6. Reformular si es necesario
        # 7. Devolver respuesta estructurada
```

**Métodos principales:**

* `_load_schema()`: carga el esquema de la base desde la DB o un archivo JSON.
* `_execute_sql()`: ejecuta la sentencia SQL y devuelve los resultados.

---

## 🌐 Servidor API (`app.py`)

Se utiliza FastAPI para exponer un endpoint RESTful:

```python
@app.post("/query/{tenant_name}/{base_name}")
def query_sql(tenant_name: str, base_name: str, payload: dict):
    """
    Parámetros esperados en payload:
    - `query`: str. Consulta en lenguaje natural.
    - `history`: opcional, lista de mensajes previos.
    """

    agent = SQLAgent(db_session, tenant_name, base_name)
    result = agent.run(payload["query"])
    return result
```

Este endpoint procesa la consulta en lenguaje natural y devuelve una respuesta con el SQL generado, resultados y explicación.

---

## 🛠️ Utilidades y Scripts Auxiliares

* `borrar_todo.py`: elimina todos los datos de prueba.
* `tempCodeRunnerFile.py`: contiene pruebas temporales de desarrollo.

---

## 🚀 Uso del Proyecto

1. Iniciar el servidor:

   ```bash
   uvicorn app:app --reload
   ```

2. Cargar tenant y base de datos.

3. Ejecutar una consulta:

   ```bash
   curl -X POST "http://localhost:8000/query/cliente1/f1" \
        -H "Content-Type: application/json" \
        -d '{"query": "¿Cuáles son los pilotos con más años en F1?"}'
   ```

4. Ejemplo de respuesta esperada:

   ```json
   {
     "status": "success",
     "results": [...],
     "explanation": "Esta consulta obtiene el piloto con mayor año de ingreso..."
   }
   ```

---

## 🧪 Pruebas y Datos de Ejemplo

Dentro del directorio `data/` se incluyen:

* `f1.db`: base de datos de ejemplo con información de Fórmula 1.
* `f1_schema.json`: esquema en formato JSON correspondiente a `f1.db`.
* `tenants.db`: base de administración de *tenants* y usuarios.
