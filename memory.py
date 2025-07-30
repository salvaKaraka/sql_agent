from models import ChatMessage, Tenant
from db import get_admin_session
from config import MAX_TOKENS_CONTEXT

# Guarda un mensaje sin eliminar los anteriores
def add_message(tenant_name: str, user_id: str, role: str, content: str):
    db = get_admin_session()
    tenant = db.query(Tenant).filter_by(name=tenant_name).first()
    tenant_id = tenant.id if tenant else None

    db.add(ChatMessage(
        tenant_id=tenant_id,
        user_id=user_id,
        role=role,
        content=content
    ))
    db.commit()
    db.close()

# Carga todos los mensajes para un usuario en una sesión
def load_memory(tenant_name: str, user_id: str):
    db = get_admin_session()
    msgs = (
        db.query(ChatMessage)
          .filter_by(tenant_id=db.query(Tenant).filter_by(name=tenant_name).first().id,
                     user_id=user_id)
          .order_by(ChatMessage.timestamp.asc())
          .all()
    )
    db.close()
    return [(m.role, m.content) for m in msgs]

# Ventana contextual basada en tokens
def get_context_window(tenant_name: str, user_id: str, max_tokens=MAX_TOKENS_CONTEXT):
    messages = load_memory(tenant_name, user_id)
    total_tokens = 0
    context = []

    def estimate_tokens(text):
        return len(text.split())

    for role, content in reversed(messages):
        tokens = estimate_tokens(content)
        if total_tokens + tokens > max_tokens:
            break
        context.insert(0, (role, content))
        total_tokens += tokens

    return context