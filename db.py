# db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Tenant, TenantDatabase
from config import ADMIN_DB_URL

# Engine y sesión para la base de administración (tenants.db)
admin_engine = create_engine(ADMIN_DB_URL)
AdminSession = sessionmaker(bind=admin_engine)

def init_admin_db():
    """Crea/abre las tablas admin: tenants + tenant_databases"""
    Base.metadata.create_all(admin_engine)

def get_admin_session():
    """Devuelve una nueva sesión a tenants.db"""
    return AdminSession()

def get_tenant_db(tenant_name: str, base_name: str):
    db = AdminSession()
    
    entry = (
        db.query(TenantDatabase)
          .join(Tenant)
          .filter(Tenant.name == tenant_name, TenantDatabase.base_name == base_name)
          .first()
    )
    
    db.close()
    if not entry:
        raise ValueError(f"No se encontró base '{base_name}' para tenant '{tenant_name}'")
    
    path = entry.db_path
    engine_t = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False}) #sacar check_same_thread si no es sqlite
    return sessionmaker(bind=engine_t)


def get_schema_info(tenant_name: str, base_name: str) -> dict:
    db = get_admin_session()

    result = (
        db.query(TenantDatabase)
        .join(Tenant)
        .filter(Tenant.name == tenant_name, TenantDatabase.base_name == base_name)
        .first()
    )

    db.close()

    if not result:
        raise Exception(f"No se encontró la base {base_name} para el tenant {tenant_name}")

    return result.schema_info or {}


def create_tenant(name: str):
    db = AdminSession()
    tenant = Tenant(name=name)
    db.add(tenant)
    db.commit()
    db.close()

def register_tenant_database(tenant_name: str, base_name: str, db_path: str, schema_info: dict):
    print("Registrando nueva base...")
    
    #cuando estemos en producción, db_path debe ser una ruta absoluta sin lo de sqlite:///
    if not db_path.startswith("sqlite:///"):
        if not db_path.startswith("./"):
            db_path = f"./{db_path}"

    db = AdminSession()

    tenant = db.query(Tenant).filter_by(name=tenant_name).first()
    if not tenant:
        tenant = Tenant(name=tenant_name)
        db.add(tenant)
        db.commit()

    existing = db.query(TenantDatabase).filter_by(tenant_id=tenant.id, base_name=base_name).first()

    if existing:
        print("Ya existe, actualizando...")
        existing.db_path = db_path
        existing.schema_info = schema_info
    else:
        print("No existe, creando...")
        new_entry = TenantDatabase(
            tenant_id=tenant.id,
            base_name=base_name,
            db_path=db_path,
            schema_info=schema_info
        )
        db.add(new_entry)

    db.commit()
    db.close()
    print("Registro completado.")


def list_tenant_databases(tenant_name: str):
    db = AdminSession()
    tenant = db.query(Tenant).filter_by(name=tenant_name).first()
    if not tenant:
        db.close()
        return []

    bases = (
        db.query(TenantDatabase)
        .filter_by(tenant_id=tenant.id)
        .all()
    )
    db.close()
    return [(b.base_name, b.db_path) for b in bases]

