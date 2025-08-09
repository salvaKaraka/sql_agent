# memory.py
# Cache volátil en memoria (por proceso)

from collections import defaultdict
from datetime import datetime, timedelta

# Cache de agentes activos: {(tenant, base): agente}
AGENT_CACHE = {}

# Historial en memoria (temporal) — solo para rendimiento
# Guardamos: (role, content, timestamp, tokens_prompt, tokens_completion, used_cache)
CONTEXT_CACHE = defaultdict(list)
CONTEXT_TTL = timedelta(hours=1)  # Expira en 1 hora


# memory.py
from db import get_admin_session
from models import ChatMessage, Tenant
from datetime import datetime

def add_message(
    tenant_name: str,
    user_id: int,
    role: str,
    content: str,
    tokens_prompt: int = None,
    tokens_completion: int = None,
    used_cache: bool = False
):
    """Guarda el mensaje tanto en memoria (para contexto rápido) como en la base de datos."""

    # Guardar en cache volátil (opcional)
    CONTEXT_CACHE[(tenant_name, user_id)].append(
        (role, content, datetime.utcnow(), tokens_prompt, tokens_completion, used_cache)
    )

    # Guardar en la base de datos
    db = get_admin_session()
    tenant = db.query(Tenant).filter_by(name=tenant_name).first()
    if tenant:
        msg = ChatMessage(
            tenant_id=tenant.id,
            user_id=user_id,
            role=role,
            content=content,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            used_cache=used_cache
        )
        db.add(msg)
        db.commit()
    db.close()



def get_context_window(tenant_name: str, user_id: int, window_size: int = 5):
    """Devuelve la ventana de contexto reciente (role, content)."""
    now = datetime.utcnow()
    msgs = [
        (r, c) for r, c, ts, _, _, _ in CONTEXT_CACHE.get((tenant_name, user_id), [])
        if now - ts < CONTEXT_TTL
    ]
    return msgs[-window_size:]


def clear_context(tenant_name: str, user_id: int):
    """Limpia el historial en memoria de un usuario."""
    CONTEXT_CACHE.pop((tenant_name, user_id), None)
