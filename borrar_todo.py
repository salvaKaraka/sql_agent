
from models import Base
from db import admin_engine  # Import admin_engine from db

# Esto borra y recrea toda la tabla
Base.metadata.drop_all(bind=admin_engine)
Base.metadata.create_all(bind=admin_engine)
