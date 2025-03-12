from pydantic import BaseModel, HttpUrl, condecimal
from sqlalchemy import Column, Integer, String
from app.database import Base
from typing import List, Optional
from datetime import datetime

# Modelo para la base de datos
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

# Modelo Pydantic para recibir datos de facturas
class FacturaData(BaseModel):
    procesoId: int
    esValido: bool
    codigoUnicoValidacion: str
    fechaValidacion: datetime
    numDocumentoIdObligado: str
    numeroDocumento: str
    fechaEmision: datetime
    totalFactura: condecimal(max_digits=12, decimal_places=2)
    cantidadUsuarios: int
    cantidadAtenciones: int
    totalValorServicios: condecimal(max_digits=12, decimal_places=2)
    identificacionAdquiriente: str
    codigoPrestador: str
    modalidadPago: str
    numDocumentoReferenciado: Optional[str]
    urlJson: Optional[HttpUrl]
    urlXml: Optional[HttpUrl]
    jsonFile: Optional[str]
    xmlFileBase64: Optional[str]
    resultadosValidacion: List
