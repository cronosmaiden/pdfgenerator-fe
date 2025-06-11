# app/services/pdf_parser.py

import re
from io import BytesIO

import pdfplumber
import requests


def fetch_pdf_bytes(pdf_url) -> BytesIO:
    """
    Descarga el PDF desde la URL (puede ser str o HttpUrl) y devuelve un BytesIO con su contenido.
    Lanza ValueError si la URL no termina en .pdf, o HTTPError si la petición falla.
    """
    url_str = str(pdf_url)
    if not url_str.lower().endswith(".pdf"):
        raise ValueError("La URL proporcionada no parece ser un PDF válido.")

    resp = requests.get(url_str, timeout=15)
    resp.raise_for_status()
    return BytesIO(resp.content)


def extract_text_from_pdf(file_stream: BytesIO) -> str:
    """
    Abre el PDF en memoria con pdfplumber y extrae todo el texto concatenado
    de la primera página (donde está la información del RUT).
    """
    with pdfplumber.open(file_stream) as pdf:
        page = pdf.pages[0]
        texto = page.extract_text() or ""
    return texto


def parse_rut_text(texto: str) -> dict:
    """
    Recorre el texto extraído del RUT (primera página) y busca, mediante expresiones regulares,
    cada campo relevante del RUT. Devuelve un diccionario con claves:
      - nit
      - dv
      - direccion_seccional          (campo 12)
      - tipo_contribuyente           (campo 24, solo código numérico)
      - tipo_documento_descripcion   (campo 25, texto)
      - tipo_documento_codigo        (campo 25, dos dígitos)
      - numero_identificacion        (campo 26)
      - primer_apellido              (campo 31)
      - segundo_apellido             (campo 32)
      - primer_nombre                (campo 33)
      - otros_nombres                (campo 34)
      - pais                         (campo 38)
      - departamento                 (campo 39)
      - ciudad_municipio             (campo 40)
      - direccion_principal          (campo 41)
    """
    resultado = {}

    # ————————————————————————————————
    # Primero: capturas directas con regex sobre el texto completo
    # ————————————————————————————————

    # 31. Primer apellido
    m31 = re.search(
        r'31\.\s*Primer apellido\s+([A-ZÁÉÍÓÚÑ0-9\-\s]+)',
        texto,
        re.IGNORECASE
    )
    if m31:
        resultado["primer_apellido"] = m31.group(1).strip()

    # 32. Segundo apellido
    m32 = re.search(
        r'32\.\s*Segundo apellido\s+([A-ZÁÉÍÓÚÑ0-9\-\s]+)',
        texto,
        re.IGNORECASE
    )
    if m32:
        resultado["segundo_apellido"] = m32.group(1).strip()

    # 33. Primer nombre
    m33 = re.search(
        r'33\.\s*Primer nombre\s+([A-ZÁÉÍÓÚÑ0-9\-\s]+)',
        texto,
        re.IGNORECASE
    )
    if m33:
        resultado["primer_nombre"] = m33.group(1).strip()

    # 34. Otros nombres
    m34 = re.search(
        r'34\.\s*Otros nombres\s+([A-ZÁÉÍÓÚÑ0-9\-\s]+)',
        texto,
        re.IGNORECASE
    )
    if m34:
        resultado["otros_nombres"] = m34.group(1).strip()

    # 38. País
    m38 = re.search(
        r'38\.\s*País\s+([A-ZÁÉÍÓÚÑ0-9\-\s]+)',
        texto,
        re.IGNORECASE
    )
    if m38:
        resultado["pais"] = m38.group(1).strip()

    # 39. Departamento
    m39 = re.search(
        r'39\.\s*Departamento\s+([A-ZÁÉÍÓÚÑ0-9\-\s]+)',
        texto,
        re.IGNORECASE
    )
    if m39:
        resultado["departamento"] = m39.group(1).strip()

    # 40. Ciudad/Municipio
    m40 = re.search(
        r'40\.\s*Ciudad\/Municipio\s+([A-ZÁÉÍÓÚÑ0-9\-\s]+)',
        texto,
        re.IGNORECASE
    )
    if m40:
        resultado["ciudad_municipio"] = m40.group(1).strip()

    # 41. Dirección principal
    m41 = re.search(
        r'41\.\s*Dirección principal\s+([A-ZÁÉÍÓÚÑ0-9,#\.\-\s]+)',
        texto,
        re.IGNORECASE
    )
    if m41:
        resultado["direccion_principal"] = m41.group(1).strip()

    # ————————————————————————————————
    # Después: recorremos línea a línea para los campos que requieren lógica adicional
    # ————————————————————————————————

    lines = texto.splitlines()
    for i, line in enumerate(lines):
        # 1) NIT y DV (campo 5 y 6)
        if line.strip().startswith("5. Número de Identificación Tributaria"):
            if i + 1 < len(lines):
                siguiente = lines[i + 1].strip()
                tokens = siguiente.split()
                # Extraemos todos los tokens puramente numéricos consecutivos
                digits_seq = []
                for t in tokens:
                    if t.isdigit():
                        digits_seq.append(t)
                    else:
                        break
                combined = "".join(digits_seq)  # e.g. "523900982"
                if len(combined) >= 2:
                    resultado["nit"] = combined[:-1]  # "52390098"
                    resultado["dv"] = combined[-1]    # "2"

                # Después de esos dígitos, capturamos DIRECCIÓN SECCIONAL (campo 12)
                direccion_tokens = []
                buscando_letras = False
                for t in tokens:
                    if t.isdigit():
                        # si no hemos arrancado a capturar letras, ignoramos dígitos
                        if not buscando_letras:
                            continue
                        # si ya empezamos a capturar letras y vemos dígitos: rompemos
                        break
                    else:
                        # token con letras => empieza la dirección seccional
                        if re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", t):
                            buscando_letras = True
                            direccion_tokens.append(t)
                        else:
                            # si ya estaba capturando letras y aparece puntuación, la agregamos
                            if buscando_letras:
                                direccion_tokens.append(t)

                if direccion_tokens:
                    resultado["direccion_seccional"] = " ".join(direccion_tokens).strip()
            continue  # ya procesamos esta sección

        # 2) Tipo de contribuyente + Tipo de documento (campo 24 y 25)
        if "24. Tipo de contribuyente" in line:
            if i + 1 < len(lines):
                siguiente = lines[i + 1].strip()
                tokens = siguiente.split()

                # 2.1) Primer token puramente numérico: código de tipo de contribuyente
                tipo_contrib = next((t for t in tokens if t.isdigit()), None)
                resultado["tipo_contribuyente"] = tipo_contrib

                if tipo_contrib:
                    idx_tc = tokens.index(tipo_contrib)
                    descr_tokens = []
                    code_tokens = []
                    capturando_descr = True

                    for t in tokens[idx_tc + 1 :]:
                        if t.isdigit():
                            capturando_descr = False
                            code_tokens.append(t)
                        else:
                            if not capturando_descr:
                                break
                            if re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", t):
                                descr_tokens.append(t)
                            else:
                                # tal vez espacios o puntuación en la descripción
                                if descr_tokens:
                                    descr_tokens.append(t)

                    resultado["tipo_documento_descripcion"] = " ".join(descr_tokens).strip()
                    if code_tokens:
                        # Unimos los dos primeros tokens numéricos para obtener, p.ej., "13"
                        resultado["tipo_documento_codigo"] = "".join(code_tokens[:2])
            continue

        # 3) Número de Identificación (campo 26)
        if "26. Número de Identificación" in line:
            if i + 1 < len(lines):
                siguiente = lines[i + 1].strip()
                tokens = siguiente.split()
                numero_id = next((t for t in tokens if t.isdigit() and 7 <= len(t) <= 11), None)
                resultado["numero_identificacion"] = numero_id
            continue

    return resultado


def pdf_to_json_rut(pdf_url: str) -> dict:
    """
    Toma la URL pública de un PDF (RUT), lo descarga, extrae texto y parsea campos.
    Retorna un diccionario con todos los datos encontrados.
    """
    fichero = fetch_pdf_bytes(pdf_url)
    texto = extract_text_from_pdf(fichero)
    datos = parse_rut_text(texto)
    return datos
