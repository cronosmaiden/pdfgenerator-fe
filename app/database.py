from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import Config

# Crear el motor de la base de datos
engine = create_engine(Config.DATABASE_URL, connect_args={"check_same_thread": False})

# Crear la sesión
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base de datos declarativa
Base = declarative_base()
