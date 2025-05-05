from pydantic import BaseModel, HttpUrl, condecimal, AnyHttpUrl
from sqlalchemy import Column, Integer, String
from app.database import Base
from typing import List, Optional, Any
from datetime import datetime

# Modelo para la base de datos
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

class Emisor(BaseModel):
    documento: str
    razon_social: str
    direccion: str
    pais: str
    departamento: str
    ciudad: str
    telefono: str
    num_celular: Optional[str] = ""
    email: str
    sitio_web: Optional[str] = ""
    regimen: str
    responsable_iva: str
    actividad_economica: str
    tarifa_ica: str
    logo: Optional[str] = None

class Documento(BaseModel):
    identificacion: str
    fecha: str
    hora: str
    moneda: str
    metodo_de_pago: str
    condicion_de_pago: Optional[str] = ""
    tipo_de_pago: Optional[str] = ""
    numero_orden: Optional[str] = ""
    fecha_vencimiento: str
    marca_agua: Optional[str] = ""
    cufe: str
    fecha_validacion_dian: str
    qr: Optional[str] = ""
    titulo_tipo_documento: str
    son: str
    notas_pie_pagina: str
    ruta_documento: HttpUrl

class EncabezadoCaracteristicas(BaseModel):
    solo_primera_pagina: int
    Color_texto: str

class PieDePagina(BaseModel):
    solo_primera_pagina: str
    Color_texto: str

class Totales(BaseModel):
    solo_ultima_pagina: int

class Caracteristicas(BaseModel):
    encabezado: EncabezadoCaracteristicas
    totales: Totales
    pie_de_pagina: PieDePagina
    papel: str
    plantilla: str
    color_fondo: str

class Receptor(BaseModel):
    ciudad: str
    correo_electronico: str
    departamento: str
    direccion: str
    identificacion: str
    nombre: str
    numero_movil: str
    pais: str

# 📌 Modelo de Detalle de Factura
class CargoDescuento(BaseModel):
    es_descuento: bool
    porcentaje_cargo_descuento: Optional[str] = "0.00"
    valor_base_cargo_descuento: Optional[str] = "0.00"
    valor_cargo_descuento: Optional[str] = "0.00"

class ValoresUnitarios(BaseModel):
    valor_descuento: Optional[str] = "0.00"
    valor_con_descuento: Optional[str] = "0.00"
    valor_impuesto_1: Optional[str] = "0.00"
    valor_impuesto_2: Optional[str] = "0.00"
    valor_impuesto_3: Optional[str] = "0.00"
    valor_impuesto_4: Optional[str] = "0.00"
    valor_reteiva: Optional[str] = "0.00"
    valor_retefuente: Optional[str] = "0.00"
    valor_reteica: Optional[str] = "0.00"
    valor_a_pagar: Optional[str] = "0.00"

class Regalo(BaseModel):
    es_regalo: bool = False
    cod_precio_referencia: Optional[int] = 0
    precio_referencia: Optional[str] = "0.00"

class ImpuestoDetalle(BaseModel):
    codigo_impuesto: Optional[int] = 0
    porcentaje_impuesto: Optional[str] = "0.00"
    valor_base_impuesto: Optional[str] = "0.00"
    valor_impuesto: Optional[str] = "0.00"

class RetencionDetalle(BaseModel):
    codigo: Optional[int] = 0
    porcentaje: Optional[str] = "0.00"
    valor_base: Optional[str] = "0.00"
    valor_retenido: Optional[str] = "0.00"

class InformacionAdicional(BaseModel):
    variable: Optional[str] = None
    valor: Optional[str] = None

class DetalleFactura(BaseModel):
    numero_linea: int
    cantidad: int
    unidad_medida: Optional[str] = ""
    unidad_de_cantidad: Optional[str] = ""  # Adaptación flexible
    nombre_unidad_medida: Optional[str] = ""
    valor_unitario: str
    descripcion: str
    nota_detalle: Optional[str] = ""
    cargo_descuento: Optional[CargoDescuento] = None
    regalo: Optional[Regalo] = Regalo()
    impuestos_detalle: Optional[ImpuestoDetalle] = None
    retenciones_detalle: Optional[List[RetencionDetalle]] = None
    valor_total_detalle_con_cargo_descuento: Optional[str] = "0.00"
    valor_total_detalle: str
    informacion_adicional: Optional[List[InformacionAdicional]] = None
    marca: Optional[str] = ""
    modelo: Optional[str] = ""
    valores_unitarios: Optional[ValoresUnitarios] = None

class ValoresTotales(BaseModel):
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
    total_documento: str
    valor_total_a_pagar: str

class Otros(BaseModel):
    resolucion: str
    salud_1: str
    salud_2: str
    salud_3: str
    salud_4: str
    salud_5: str
    salud_6: str
    salud_7: Optional[str] = ""
    salud_8: str
    salud_9: str
    salud_10: str
    salud_11: str
    documento_referencia: Optional[str] = ""
    informacion_adicional: Optional[str] = ""

class Afacturar(BaseModel):
    titulo_superior: str
    logo: Optional[str] = ""
    info_pt: str

class FacturaRequest(BaseModel):
    emisor: Emisor
    documento: Documento
    caracteristicas: Caracteristicas
    receptor: Receptor
    detalles: List[DetalleFactura]
    valores_totales: ValoresTotales
    otros: Otros
    afacturar: Afacturar
