from app.database import SessionLocal
from app.models import User
from app.services.auth import get_password_hash

def create_user(username: str, password: str):
    db = SessionLocal()

    try:
        # Verificar si el usuario ya existe
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            print(f"⚠️ El usuario '{username}' ya existe.")
            return

        # Crear el usuario con la contraseña hasheada
        hashed_password = get_password_hash(password)
        new_user = User(username=username, hashed_password=hashed_password)
        
        # Guardar en la base de datos
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        print(f"✅ Usuario '{username}' creado con éxito.")
    except Exception as e:
        print(f"❌ ERROR: No se pudo crear el usuario. {e}")
    finally:
        db.close()

# Ejecutar el script para crear un usuario manualmente
if __name__ == "__main__":
    username = "admin"  # Cambia esto si deseas otro usuario
    password = "admin123"
    create_user(username, password)
