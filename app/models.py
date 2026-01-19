from pydantic import BaseModel, HttpUrl, AnyUrl, Field, field_validator
from sqlalchemy import Column, Integer, String
from app.database import Base
from typing import List, Optional

# -------------------------------
# Modelo para la base de datos
# -------------------------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

# -------------------------------
# Requests básicos
# -------------------------------
class PdfToJsonRequest(BaseModel):
    pdf_url: HttpUrl

# -------------------------------
# Emisor
# -------------------------------
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

# -------------------------------
# Documento (común factura / nómina)
# -------------------------------
class Documento(BaseModel):
    identificacion: str
    fecha: str
    hora: str
    moneda: str
    metodo_de_pago: str
    condicion_de_pago: Optional[str] = ""
    tipo_de_pago: Optional[str] = ""
    banco: Optional[str] = ""
    cuenta_bancaria: Optional[str] = ""
    cune: Optional[str] = ""
    numero_orden: Optional[str] = ""
    fecha_vencimiento: Optional[str] = ""
    marca_agua: Optional[str] = ""
    cufe: str
    fecha_validacion_dian: str
    qr: Optional[str] = ""
    titulo_tipo_documento: str
    son: str
    notas_pie_pagina: Optional[str] = ""
    notas_adicionales: Optional[str] = ""
    ruta_documento: Optional[AnyUrl] = Field(
        None,
        description="URL del PDF existente; si viene vacía o ausente, se generará automáticamente"
    )

    @field_validator("ruta_documento", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("notas_adicionales", mode="before")
    @classmethod
    def truncate_notas_adicionales(cls, v):
        if isinstance(v, str):
            return v[:800]
        return v

# -------------------------------
# Características
# -------------------------------
class EncabezadoCaracteristicas(BaseModel):
    solo_primera_pagina: int
    Color_texto: str

class PieDePagina(BaseModel):
    solo_primera_pagina: str
    Color_texto: str

class Totales(BaseModel):
    solo_ultima_pagina: int

class ColoresPersonalizados(BaseModel):
    # nuevos colores para plantilla 3
    color_info: Optional[str] = None
    color_negativo: Optional[str] = None
    color_positivo: Optional[str] = None

class Caracteristicas(BaseModel):
    encabezado: EncabezadoCaracteristicas
    totales: Totales
    pie_de_pagina: PieDePagina
    papel: str
    plantilla: str
    color_fondo: str
    # subsección opcional con colores por sección (solo aplica a plantilla 3)
    color_personalizado_campos: Optional[ColoresPersonalizados] = None

# -------------------------------
# Receptor
# -------------------------------
class Receptor(BaseModel):
    ciudad: str
    correo_electronico: str
    departamento: str
    direccion: str
    identificacion: str
    nombre: str
    numero_movil: str
    pais: str
    cargo: Optional[str] = ""
    tipo_contrato: Optional[str] = ""

# -------------------------------
# Factura (plantilla 1 y 2)
# -------------------------------
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
    unidad_de_cantidad: Optional[str] = ""
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

# -------------------------------
# Nómina (plantilla 3)
# -------------------------------
class Devengo(BaseModel):
    tipo: str
    valor: str
    descripcion: str

class Deduccion(BaseModel):
    tipo: str
    valor: str
    descripcion: str

class AportesEmpleador(BaseModel):
    tipo: str
    valor: str
    descripcion: str

class PrestacionesSociales(BaseModel):
    tipo: str
    valor: str
    descripcion: str

class ValorNomina(BaseModel):
    valor_base: str
    valor_total_devengos: Optional[str] = "0.00"
    valor_total_deducciones: Optional[str] = "0.00"
    valor_total_empleador: Optional[str] = "0.00"
    valor_total_prestaciones: Optional[str] = "0.00"
    valor_total_pago: Optional[str] = "0.00"

# -------------------------------
# Otros (unificado para factura y nómina)
# -------------------------------
class Otros(BaseModel):
    # Factura
    resolucion: Optional[str] = ""
    salud_1: Optional[str] = ""
    salud_2: Optional[str] = ""
    salud_3: Optional[str] = ""
    salud_4: Optional[str] = ""
    salud_5: Optional[str] = ""
    salud_6: Optional[str] = ""
    salud_7: Optional[str] = ""
    salud_8: Optional[str] = ""
    salud_9: Optional[str] = ""
    salud_10: Optional[str] = ""
    salud_11: Optional[str] = ""
    documento_referencia: Optional[str] = ""
    informacion_adicional: Optional[str] = ""

    # Nómina
    variable_1: Optional[str] = ""
    variable_2: Optional[str] = ""
    variable_3: Optional[str] = ""

# -------------------------------
# Afacturar
# -------------------------------
class Afacturar(BaseModel):
    titulo_superior: str
    logo: Optional[str] = ""
    info_pt: str

# -------------------------------
# FacturaRequest (unificado)
# -------------------------------
class FacturaRequest(BaseModel):
    emisor: Emisor
    documento: Documento
    caracteristicas: Caracteristicas
    receptor: Receptor

    # Factura
    detalles: List[DetalleFactura] = Field(default_factory=list)
    valores_totales: Optional[ValoresTotales] = None

    # Nómina
    devengos: List[Devengo] = Field(default_factory=list)
    deducciones: List[Deduccion] = Field(default_factory=list)
    aportes_empleador: List[AportesEmpleador] = Field(default_factory=list)
    prestaciones_sociales: List[PrestacionesSociales] = Field(default_factory=list)
    valor_nomina: Optional[ValorNomina] = None

    otros: Otros
    afacturar: Afacturar
