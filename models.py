from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON
import datetime

Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"
    id      = Column(Integer, primary_key=True)
    name    = Column(String, unique=True, nullable=False)

class TenantDatabase(Base):
    __tablename__ = "tenant_databases"
    id          = Column(Integer, primary_key=True)
    tenant_name = Column(String, nullable=False)  # coincide con Tenant.name
    base_name   = Column(String, nullable=False)  # p.ej. "ventas", "rrhh"
    schema_info = Column(JSON)  # JSON string con descripciones de tablas
    db_path     = Column(String, nullable=False) # ruta al SQLite de este tenant

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id          = Column(Integer, primary_key=True)
    tenant_id   = Column(Integer, ForeignKey("tenants.id"))
    session_id  = Column(String, index=True)
    role        = Column(String)   # "user" o "assistant"
    content     = Column(Text)
    timestamp   = Column(DateTime, default=datetime.datetime.utcnow)

    tenant      = relationship("Tenant", backref="messages")
