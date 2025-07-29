# memory.py
from models import ChatMessage, Tenant
from db import get_admin_session
from config import MEMORY_WINDOW

def add_message(tenant_name: str, session_id: str, role: str, content: str):
    db = get_admin_session()

    tenant = db.query(Tenant).filter_by(name=tenant_name).first()
    tenant_id = tenant.id if tenant else None

    db.add(ChatMessage(
        tenant_id=tenant_id,
        session_id=session_id,
        role=role,
        content=content
    ))
    db.commit()

    # Mantener solo los últimos N mensajes por sesión
    msgs = (
        db.query(ChatMessage)
          .filter_by(session_id=session_id)
          .order_by(ChatMessage.timestamp.desc())
          .all()
    )
    for old in msgs[MEMORY_WINDOW:]:
        db.delete(old)
    db.commit()
    db.close()

def load_memory(tenant_name: str, session_id: str):
    db = get_admin_session()
    msgs = (
        db.query(ChatMessage)
          .filter_by(session_id=session_id)
          .order_by(ChatMessage.timestamp.asc())
          .all()
    )
    db.close()
    return [(m.role, m.content) for m in msgs]
