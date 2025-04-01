from pydantic import BaseModel, HttpUrl, condecimal, AnyHttpUrl
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

# 📌 Modelo de Detalle de Factura
class CargoDescuento(BaseModel):
    es_descuento: bool
    porcentaje_cargo_descuento: Optional[str] = "0.00"
    valor_base_cargo_descuento: Optional[str] = "0.00"
    valor_cargo_descuento: Optional[str] = "0.00"

class Regalo(BaseModel):
    es_regalo: bool = False
    cod_precio_referencia: Optional[int] = 0
    precio_referencia: Optional[str] = "0.00"

class ImpuestoDetalle(BaseModel):
    codigo_impuesto: str
    porcentaje_impuesto: Optional[str] = "0.00"
    valor_base_impuesto: Optional[str] = "0.00"
    valor_impuesto: Optional[str] = "0.00"

class RetencionDetalle(BaseModel):
    codigo: Optional[int] = 0
    porcentaje: Optional[str] = "0.00"
    valor_base: Optional[str] = "0.00"
    valor_retenido: Optional[str] = "0.00"

class DetalleFactura(BaseModel):
    numero_linea: int
    cantidad: int
    unidad_de_cantidad: str
    valor_unitario: str
    descripcion: str
    cargo_descuento: Optional[CargoDescuento] = None
    regalo: Optional[Regalo] = Regalo() 
    impuestos_detalle: Optional[ImpuestoDetalle] = None
    retenciones_detalle: Optional[List[RetencionDetalle]] = None
    valor_total_detalle_con_cargo_descuento: Optional[str] = "0.00"
    valor_total_detalle: str

# 📌 Modelo de Información del Adquiriente
class NombreAdquiriente(BaseModel):
    razon_social: str
    primer_nombre: Optional[str] = ""
    segundo_nombre: Optional[str] = ""
    apellido: Optional[str] = ""

class RUT(BaseModel):
    resp_calidades_atributos: List[str]
    usuario_aduanero: List[str]

class InformacionAdquiriente(BaseModel):
    tipo_contribuyente: int
    tipo_regimen: int
    tipo_identificacion: int
    identificacion: str
    correo_electronico: str
    numero_movil: str
    nombre: NombreAdquiriente
    pais: str
    departamento: str
    ciudad: str
    zona: Optional[str] = ""
    direccion: str
    RUT: RUT

# 📌 Modelo de Encabezado
class Encabezado(BaseModel):
    documento: str
    fecha: str
    hora: str
    moneda: str
    metodo_de_pago: Optional[str] = ""
    fecha_vencimiento: str
    nota: Optional[List[str]] = []  # Lista de notas opcional
    tipo_factura: Optional[int] = 1
    tipo_de_pago: Optional[str] = ""
    numero_orden: Optional[str] = ""  # Puede estar vacío
    numero_resolucion_facturacion: Optional[str] = "000000"

# 📌 Modelo de Totales
class ValorFactura(BaseModel):
    valor_base: str
    valor_base_calculo_impuestos: str
    valor_base_mas_impuestos: str
    valor_anticipo: str
    valor_descuento_total: str
    valor_total_recargos: str
    valor_total_impuesto_1: str
    valor_total_impuesto_2: str
    valor_total_impuesto_3: str
    valor_total_impuesto_4: str
    valor_total_reteiva: str
    valor_total_retefuente: str
    valor_total_reteica: str
    total_factura: str
    valor_total_a_pagar: str

# 📌 Modelo de Datos del Obligado
class DatosObligado(BaseModel):
    documento_obligado: str
    razon_social: str
    direccion: str
    depto_ciudad: str
    telefono: str
    num_celular: Optional[str] = ""
    email: str
    sitio_web: Optional[str] = ""
    regimen: str
    responsable_iva: str
    actividad_economica: str
    tarifa_ica: str

# 📌 Modelo de Datos del Documento
class DatosDocumento(BaseModel):
    ruta_documento: AnyHttpUrl
    logo: str
    plantilla: str
    color: str
    papel: str

# 📌 Modelo de Datos Adicionales
class DatosAdicionales(BaseModel):
    son: str
    titulo: str
    notas_pie_pagina: str
    resolucion: str
    salud_1: str
    salud_2: str
    salud_3: str
    salud_4: str
    salud_5: str
    salud_6: str
    salud_7: str
    salud_8: str
    salud_9: str
    salud_10: str
    salud_11: str

# 📌 Modelo Completo de Factura
class Factura(BaseModel):
    encabezado: Encabezado
    informacion_adquiriente: InformacionAdquiriente
    detalle_factura: List[DetalleFactura]
    valor_factura: ValorFactura
    entorno: Optional[str] = ""
    datos_obligado: DatosObligado
    datos_documento: DatosDocumento
    datos_adicionales: DatosAdicionales
    cufe: str
    fecha_validacion_dian: str
    qr: str

# 📌 Modelo para recibir el JSON completo
class FacturaRequest(BaseModel):
    facturas: List[Factura]
