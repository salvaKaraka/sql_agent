import os
from dotenv import load_dotenv

load_dotenv()

# Número de mensajes que se guardan por sesion
MEMORY_WINDOW = int(os.getenv("MEMORY_WINDOW", 10))

# Directorio de memorias
MEMORY_DIR = os.getenv("MEMORY_DIR", "./.memories")

# LLM
LLM_MODEL = "gemini-2.5-flash"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Base de datos administrativa
ADMIN_DB_URL = os.getenv("ADMIN_DB_URL", "sqlite:///./data/tenants.db")
