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

class ColeccionSector(BaseModel):
    nombre: Optional[str] = None
    informacion_adicional: Optional[List[InformacionAdicional]] = []

class Sector(BaseModel):
    tipo: Optional[str] = None
    tipo_operacion: Optional[str] = None
    coleccion: Optional[List[ColeccionSector]] = []

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
    informacion_adicional: Optional[List[InformacionAdicional]] = None

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
    id_factura: str
    fecha: str
    hora: str
    moneda: str
    metodo_de_pago: Optional[str] = ""
    fecha_vencimiento: str
    nota: Optional[List[Any]] = []
    tipo_factura: Optional[int] = 1
    tipo_de_pago: Optional[str] = ""
    numero_orden: Optional[str] = ""  # Puede estar vacío
    numero_resolucion_facturacion: Optional[str] = "000000"
    prefijo: Optional[str] = ""


# 📌 Modelo de Periodo de Facturación
class PeriodoFacturacion(BaseModel):
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None

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
    logo_ofe: Optional[str] = "iVBORw0KGgoAAAANSUhEUgAAAIcAAACHCAMAAAF8PoquAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAALlUExURf///7CwsFZWVlxcXFtbW19fX+Dg4JeXl1VVVZSUlOLi4mBgYFpaWo6OjoWFhQAAAAcHB9DQ0F5eXtPT0wgICFFRUYiIiHl5ecvLy8TExMXFxfT09MzMzM7Ozt/f3/b29s/Pz93d3YSEhJ2dnaqqqpycnKmpqYeHh5ubm4+PjwQEBKKioq+vrwYGBubm5vf39/7+/vn5+fHx8erq6t7e3uTk5Pv7+/z8/OXl5enp6dvb2zY2Ni0tLS8vLzk5OcPDwzc3NzMzM4yMjMjIyDQ0NHV1ddzc3EFBQTU1NVlZWXt7eyEhIRAQECgoKPj4+NfX1xkZGQ8PDxMTEzg4OLq6uhQUFBcXF1RUVNLS0tTU1AkJCQ4ODrKysmxsbE1NTfX19WZmZqampqenpxgYGNjY2CYmJh4eHh0dHQMDAysrK7Ozs29vb7u7u05OTikpKZ6enkVFRbm5uWtraxUVFTIyMvLy8u3t7SMjIyoqKu7u7vDw8IODg2hoaPr6+srKysfHxwICAiIiIiAgIDo6Os3NzQsLC9ra2l1dXa2trQwMDB8fH/39/QoKCk9PT2dnZ2FhYdXV1dbW1lBQUOvr6+Hh4be3t+zs7Ojo6KysrJmZmby8vOPj45CQkIuLi3BwcLi4uK6urmNjY7W1taGhoUhISL6+vrS0tBsbG5aWlpqamm5ubkJCQo2NjUNDQ2VlZaWlpZiYmMHBwQUFBVJSUkxMTAEBAX5+frGxsS4uLoqKioCAgJKSkjw8PEBAQHd3d9nZ2ZGRkZ+fn+/v71hYWBISEqCgoFNTU+fn51dXV/Pz83R0dHh4eCUlJaurq3FxcRoaGhEREWlpaaOjo7+/v8LCwj8/PywsLH19fXNzc3x8fG1tbUZGRnp6eiQkJA0NDYmJicDAwKSkpCcnJ2JiYj09PRwcHMnJycbGxkRERHZ2djExMUdHRzs7O4KCgoGBgT4+PhYWFqioqIaGhpOTk9HR0UlJSQAAAIJ61T0AAAD3dFJOU////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////wDuZjaTAAAACXBIWXMAABcRAAAXEQHKJvM/AAAHs0lEQVRoQ+1bwbWjOBDUkZtunLjwHomQiQMgAR0Jg2SIgTAIY6uqhUE2YGzj2dm31PeAJKRW0Wq1WrLHfYpCn7J0RelcHgtX0KCSG2JGQEnhPBKV5Rd4KFmI9c4j59ksonYeBFgytfLDYwkyaDgsWs0ADedG5zJ8RjfihswPkReuoMakNHW+ChJ2PlSRs700/spFySGguvcl+yPQalRJ4LDFEqpqUQKwYERxLOnstkAlVQUqLf+xwj7DjnoS6xpgFhgFaUCfxEYNKEUVPCi8C75i5RnWkdpOIiwzdxR1/wBVCUreYUJgvt6VkJI0tI5KVSETq6IRmjqKXBrQjVXCYxWDDx2fNomUdYjmI45q98In6DkcoaCbgJOQEditKCbFP8/IO3bGZhVe1uJaOga4SDPdFCHI6FtcUAlW82wvSRVYYFpFRhFC7CiRMtGNVaYp4AMSkUtSZR1TldWpZvNo9dGENaXRUZKK68EkYCY9Q7ob8EJrVWyMfIYXxiKVVEnfyHMKvqjCv60q6qjQGrdVRaihVFUJa3QFrK6+kyi9OaRtIQw1LjEz44BhHqgycknpMizIWGCyjEOHG6/jjhFc+H+iumU3GgcAmyEsEywTjdQy0cJuSKbBV75jltuokgnmujOEzAhETE8I8mN2tbXhBTDPS8aRcLjA0OLCWX5zjGSKwgd8+GQfAZUgYSmkRIxovpUx6WYMsVAshTwwiUI630jI/YUedJLP035FCJxwRgK+QSlel0+IbSHyNCHrLZ3nSPRyMzeaS8hus0p2hBzH5hC/Qs39zgE0MGhLZd7XZN/Re2IKIG0e9DUGrru4Q8TYy//jCjNjKdbjrRF25awtjIavPfUKGVqVohC0R62lELPhO5aK7byv2OhRiJgkQnZGZwCNWP9zIazrYV1vC1kADYQDQrahplAidtHGCe2ho8a1TO2NzgJWS6KgYgK7GrDQ/aiQJxxyQ8QpPjbPY0xMCxIswxgZgELnTHyERHdsGl24cOHCnwOD0uimmMyy6CMZoQKWScLaEtFuTEYgjJscd7H0eygmLFMuMzxdwLKxQJo7ir9Txu9hy4ypeVp/dqAltmTMjZUXObZGSaYHHdfxAytvaLFIM6a5y8i8u3mEiIgBnG9Xzy4fMTzKQGsEzRBwGxhFI/sSWzLU/ZcyFPftyViUb8ookUhlpNKOyKBm35FxH1tcRo/wijKQQKkpRtiVUcMMuCmlUYyIEjGejNIynqgttgGbMrT77EbtawM2NRVcBSPxRj6lypZhbbwb0txRnC/j+NaqXtj68VYpGDd/iS6HxRzAmGU2vwtE69p0jjx+kEt/dOZbgA3ceL8hYfE6NkkwHCa1B3gNBPhwEwDuPbYRoPC2DO0bcId94t2x2TsoY3naMnrsMHGf9njgtCFj2QqV4p0Y4g6xeSlj2SrN4RWkhNc89mTgg4H5ggfmOwwaDb/gkaMW/33Dgxy0Of2CB60D4GHRezIWiDKqAzw2geXWNu6veWxBqkB9XKMgzFzw4njB1R+SoSGh/1ZLAlmbwTymOiTDKpkkntAAmHlcExA6HNVHgml0mPoGr2MWAzT+AdJWb7+kkLY6RQbi6Kg1C7WTTIwFk4MJxNqKCmZgOZhifibvp9JKT8tBrkeMKYByTl64cOHChQsXLvzngcjWkBykYYc4I9kh82RkxsFGOoEjtr8HyhVO/xlUF48EezyefgLxS/zJvs5D2ba1fULT1lBlU7c6ZuKzup1mQuiHwbem6SLDTrjGhhho6mEY4gnVVyjaljvUtm0Ddph2KjJtWzBtsQcndKjJ/WujvfCQ1XoU0LQFq3TifgpIU3fVxGOSOvNAt3hnPQrYRcOTwH80bMG6VvI1yINGtcajthR4oCfjgUFBWiZvLXjUeRYP3u88nsfFepr0MYTQNE3FH9t8xqPI1+rv6WMelzsP6COgahwX47EyLmW+bb05j32e8KSPtXFJ9THbB3mg5JnHvj/d4pHoY39cqI+Ux6o+PuPBO7odqgJCJ//Bgg5oOFfHgifYkI3peyvBwActrV3Z3+kuUe2sIfv6cIWddd3fAzwEjJP9dmXQ4bAt+WpSgjUwDeQS7+vjN/h7eGyPS/8LHk1djzXNNUW3o49fQJZzwkL3JRjyrpnpmeBX/M+O4aeIB9uz+YTpp2+YofGrHNVRDYXk9Gac88BpZLmYE3cNw3UuYA52k8ebq9wOJo81SSz1mvSrltJ0EA/p5mf64CBIYpzzdNtxjZNm5LfP08emH+Ow9PTRcWDEw0ZDqvqAx57/2OKhd26kFBN5Ao9P/Dp7GIyNDcw2jzX72ODx7nprwhThTJ3/O/pQr3iiBV0yFzw+tdMPeKh/SNVSodan6OODOAiy+r5XR+r9x+PS9OstErDKCeNS6P+4vQN934ltKsAUvei2Pg7Pl7choerI+qQblRJMvNY7UVJKMbRoqsmJPGSdFk/Zckd96t1tP01IxSIMnrXUZsN/Ig8Ny3Jp1yvfj/SETL+SUacTbDacx4M/d8qnH+OUPdJxvoW8boehzqQjGzcXqgxlbX3/8U7oFq1/DJ67mM2ehb/lfOxPnhfur/t/jsf++vK38IhIJprtmyOSvYj82oR0dh5otM3jwoULFy78x+HcPxpPn2fEr/yMAAAAAElFTkSuQmCC"
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

# 📌 Modelo para "impuestos"
class Impuesto(BaseModel):
    codigo_impuesto: Optional[int] = None
    porcentaje_impuesto: Optional[str] = None
    valor_base_calculo_impuesto: Optional[str] = None
    valor_total_impuesto: Optional[str] = None

# 📌 Modelo para "retenciones"
class Retencion(BaseModel):
    codigo: Optional[int] = None
    porcentaje: Optional[str] = None
    valor_base: Optional[str] = None
    valor_retenido: Optional[str] = None

# 📌 Modelo para "descuentos"
class Descuento(BaseModel):
    codigo_descuento: Optional[int] = None
    porcentaje_descuento: Optional[str] = None
    valor_base_calculo_descuento: Optional[str] = None
    valor_total_descuento: Optional[str] = None

# 📌 Modelo para "recargos"
class Recargo(BaseModel):
    nombre_recargo: Optional[str] = None
    porcentaje_recargo: Optional[str] = None
    valor_base_calculo_recargo: Optional[str] = None
    valor_total_recargo: Optional[str] = None

# 📌 Modelo Completo de Factura
class Factura(BaseModel):
    encabezado: Encabezado
    sector: Optional[Sector] = None
    periodo_facturacion: Optional[PeriodoFacturacion] = None
    informacion_adquiriente: InformacionAdquiriente
    detalle_factura: List[DetalleFactura]
    impuestos: Optional[List[Impuesto]] = None
    retenciones: Optional[List[Retencion]] = None
    descuentos: Optional[List[Descuento]] = None
    recargos: Optional[List[Recargo]] = None
    valor_factura: ValorFactura
    entorno: Optional[str] = ""
    datos_obligado: DatosObligado
    datos_documento: DatosDocumento
    datos_adicionales: DatosAdicionales
    cufe: str
    fecha_validacion_dian: str
    qr: str

class Notificacion(BaseModel):
    es_automatico: Optional[str] = None
    correo_obligado: Optional[str] = None
    asunto: Optional[str] = None
    con_copia: Optional[str] = None

# 🧩 Submodelo de Integrador
class Integrador(BaseModel):
    nombre: Optional[str] = None
    tipo: Optional[str] = None

# 📌 Modelo principal de Generalidades
class Generalidades(BaseModel):
    tipo_ambiente_dian: Optional[int] = None
    version: Optional[int] = None
    identificador_transmision: Optional[str] = None
    rg_tipo: Optional[str] = None
    rg_base_64: Optional[str] = None
    notificacion: Optional[Notificacion] = None
    integrador: Optional[Integrador] = None

# 📌 Modelo para recibir el JSON completo
class FacturaRequest(BaseModel):
    facturas: List[Factura]
    generalidades: Optional[Generalidades] = None
