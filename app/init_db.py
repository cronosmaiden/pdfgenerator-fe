from app.database import Base, engine
from sqlalchemy import inspect
from app.models import User  # Asegurar que se importe

def init_db():
    print("🔄 Creando la base de datos y tablas...")
    
    # FORZAR LA CREACIÓN
    Base.metadata.create_all(bind=engine)

    # VERIFICAR SI SE CREÓ LA TABLA USERS
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if "users" in tables:
        print("✅ La tabla 'users' fue creada correctamente.")
    else:
        print("❌ ERROR: La tabla 'users' NO SE CREÓ.")

if __name__ == "__main__":
    init_db()
