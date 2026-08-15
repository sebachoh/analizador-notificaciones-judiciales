"""Cliente del portal de Publicaciones Procesales de la Rama Judicial.

Cómo funciona el portal (verificado contra el sitio real):

1. El buscador filtra por ``idDepto`` + ``idDespacho`` (el código de 12 dígitos
   que son los primeros 12 del radicado) y un rango ``fechaInicio``/``fechaFin``.
   Devuelve una tabla de publicaciones; cada fila enlaza a una página de detalle
   identificada por ``articleId``.
2. La página de detalle lista las providencias individuales de esa publicación
   como enlaces ``get_file``, y **el nombre de cada archivo trae el año y el
   consecutivo del proceso**: ``03-2026-00036 TrasladoRecurso.pdf``.

De ahí sale la optimización que importa: se decide qué documento corresponde al
radicado **leyendo nombres de archivo**, no descargando PDFs. Solo se descargan
los que coinciden — normalmente uno o ninguno, en vez de cientos.

Notas sobre errores de la versión anterior, para no repetirlos:

* Se enviaban ``idEntidad`` e ``idEspecialidad`` tomados del radicado, pero el
  portal usa un catálogo propio y distinto para esos campos, así que el filtro
  no hacía lo esperado.
* Se buscaban enlaces ``/documents/6098902/`` en la página del listado, donde
  los únicos que hay son los del instructivo del sitio. De ahí que todos los
  resultados abrieran el mismo PDF.
"""

from __future__ import annotations

import io
import os
import re
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# PyMuPDF extrae texto varias veces más rápido que pypdf y libera el GIL
# mientras trabaja. pypdf queda como respaldo si no está instalado.
try:
    import pymupdf
except ImportError:  # pragma: no cover
    try:
        import fitz as pymupdf
    except ImportError:
        pymupdf = None

import pypdf

MOTOR_PDF = "pymupdf" if pymupdf is not None else "pypdf"

from . import cache, extractor
from .radicado import Radicado

BASE = "https://publicacionesprocesales.ramajudicial.gov.co"
INICIO = f"{BASE}/web/publicaciones-procesales/inicio"
PORTLET = (
    "co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2"
    "_INSTANCE_BIyXQFHVaYaq"
)

MAX_WORKERS = int(os.environ.get("BJC_WORKERS", "8"))
MAX_PAGINAS = int(os.environ.get("BJC_MAX_PAGINAS", "20"))
TTL_LISTADO = int(os.environ.get("BJC_TTL_LISTADO", "1800"))       # 30 minutos
TTL_DETALLE = int(os.environ.get("BJC_TTL_DETALLE", "604800"))     # 7 días
TIMEOUT = (6, 25)
MAX_BYTES_PDF = 40 * 1024 * 1024

_RE_ARTICLE_ID = re.compile(r"_articleId=(\d+)")
_RE_UUID = re.compile(
    r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})", re.IGNORECASE
)

_local = threading.local()


# --------------------------------------------------------------------------
# Sesión HTTP compartida
# --------------------------------------------------------------------------
def sesion() -> requests.Session:
    s = getattr(_local, "sesion", None)
    if s is None:
        s = requests.Session()
        adaptador = HTTPAdapter(
            max_retries=Retry(
                total=3,
                backoff_factor=0.6,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=frozenset(["GET"]),
                raise_on_status=False,
            ),
            pool_connections=MAX_WORKERS,
            pool_maxsize=MAX_WORKERS * 2,
        )
        s.mount("https://", adaptador)
        s.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                "Accept-Language": "es-CO,es;q=0.9",
            }
        )
        _local.sesion = s
    return s


# --------------------------------------------------------------------------
# Rango de fechas
# --------------------------------------------------------------------------
def rango_de_meses(meses: int, hoy: date | None = None) -> tuple[str, str]:
    """Ventana móvil que termina hoy y empieza `meses` meses atrás."""
    hoy = hoy or date.today()
    total = hoy.month - meses
    anio = hoy.year + (total - 1) // 12
    mes = (total - 1) % 12 + 1
    bisiesto = anio % 4 == 0 and (anio % 100 != 0 or anio % 400 == 0)
    dias_mes = [31, 29 if bisiesto else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(anio, mes, min(hoy.day, dias_mes[mes - 1])).isoformat(), hoy.isoformat()


# --------------------------------------------------------------------------
# Construcción de URLs del portlet
# --------------------------------------------------------------------------
def _url(**campos: str) -> str:
    params = {
        "p_p_id": PORTLET,
        "p_p_lifecycle": "0",
        "p_p_state": "normal",
        "p_p_mode": "view",
    }
    for clave, valor in campos.items():
        params[f"_{PORTLET}_{clave}"] = valor
    return f"{INICIO}?{urllib.parse.urlencode(params)}"


def _descargar_html(url: str) -> str:
    try:
        r = sesion().get(url, timeout=TIMEOUT)
        r.raise_for_status()
        return r.text
    except requests.RequestException:
        return ""


# --------------------------------------------------------------------------
# Paso 1: listado de publicaciones del despacho
# --------------------------------------------------------------------------
def listar_publicaciones(rad: Radicado, desde: str, hasta: str) -> list[dict]:
    """Publicaciones del despacho en la ventana, como [{id, titulo}]."""
    clave = f"listado|{rad.despacho_codigo}|{desde}|{hasta}"
    guardado = cache.leer_listado(clave, TTL_LISTADO)
    if isinstance(guardado, list):
        return guardado

    publicaciones: dict[str, str] = {}
    for pagina in range(1, MAX_PAGINAS + 1):
        html = _descargar_html(
            _url(
                action="busqueda",
                fechaInicio=desde,
                fechaFin=hasta,
                idDepto=rad.departamento_codigo,
                idDespacho=rad.despacho_codigo,
                verTotales="true",
                cur=str(pagina),
            )
        )
        if not html:
            break

        antes = len(publicaciones)
        sopa = BeautifulSoup(html, "html.parser")
        for enlace in sopa.select('a[href*="_articleId="]'):
            m = _RE_ARTICLE_ID.search(enlace.get("href", ""))
            if not m:
                continue
            titulo = enlace.get_text(strip=True)
            # La fila trae dos enlaces al mismo artículo: el título y
            # "VER DETALLE". Nos quedamos con el que sí describe.
            if m.group(1) not in publicaciones or (
                titulo and "VER DETALLE" not in titulo.upper()
            ):
                publicaciones[m.group(1)] = titulo

        if len(publicaciones) == antes:
            break  # no hay más páginas

    resultado = [
        {"id": id_, "titulo": titulo or "Publicación procesal"}
        for id_, titulo in publicaciones.items()
    ]
    cache.guardar_listado(clave, resultado)
    return resultado


# --------------------------------------------------------------------------
# Paso 2: documentos de cada publicación (aquí están los nombres de archivo)
# --------------------------------------------------------------------------
def documentos_de_publicacion(article_id: str) -> dict:
    """Providencias individuales de una publicación, con su nombre de archivo.

    Una publicación ya emitida no cambia, así que se cachea por varios días.
    """
    clave = f"detalle|{article_id}"
    guardado = cache.leer_listado(clave, TTL_DETALLE)
    if isinstance(guardado, dict):
        return guardado

    html = _descargar_html(_url(jspPage="/META-INF/resources/detail.jsp", articleId=article_id))
    sopa = BeautifulSoup(html, "html.parser")

    archivos = []
    for enlace in sopa.select('a[href*="get_file"]'):
        href = enlace.get("href", "")
        nombre = enlace.get_text(strip=True)
        if not nombre:
            continue
        archivos.append(
            {
                "nombre": nombre,
                "url": href if href.startswith("http") else f"{BASE}{href}",
                "uuid": (_RE_UUID.search(href).group(1).lower()
                         if _RE_UUID.search(href) else href),
            }
        )

    # PDF del estado completo (la lista de todos los procesos de ese día).
    url_estado = None
    for enlace in sopa.select('a[href*="/documents/6098902/"]'):
        href = enlace.get("href", "")
        if href.lower().endswith(".pdf") or "/documents/6098902/" in href:
            url_estado = href if href.startswith("http") else f"{BASE}{href}"
            break

    datos = {"archivos": archivos, "url_estado": url_estado}
    if archivos or url_estado:
        cache.guardar_listado(clave, datos)
    return datos


def coincide_nombre(nombre: str, rad: Radicado) -> bool:
    """¿El nombre del archivo corresponde a este radicado?

    Los nombres siguen el patrón ``<n>-<año>-<consecutivo><cuaderno> <Tipo>.pdf``.
    Como el listado ya viene filtrado por despacho, el par año + consecutivo
    identifica el proceso sin ambigüedad.
    """
    patron = rf"(?<!\d){re.escape(rad.anio)}\s*-\s*{re.escape(rad.consecutivo)}(?!\d)"
    return re.search(patron, nombre) is not None


# --------------------------------------------------------------------------
# Paso 3: descarga y lectura del documento que sí corresponde
# --------------------------------------------------------------------------
def extraer_texto(datos: bytes) -> str:
    if pymupdf is not None:
        with pymupdf.open(stream=datos, filetype="pdf") as doc:
            return "\n".join(pagina.get_text() for pagina in doc)

    lector = pypdf.PdfReader(io.BytesIO(datos))
    partes = []
    for pagina in lector.pages:
        try:
            partes.append(pagina.extract_text() or "")
        except Exception:
            continue
    return "\n".join(partes)


def texto_documento(clave: str, url: str) -> str | None:
    """Texto del PDF, desde la caché permanente o descargándolo."""
    guardado = cache.leer_texto(clave)
    if guardado is not None:
        return guardado

    try:
        with sesion().get(url, timeout=TIMEOUT, stream=True) as r:
            r.raise_for_status()
            declarado = r.headers.get("Content-Length")
            if declarado and int(declarado) > MAX_BYTES_PDF:
                return None

            datos = bytearray()
            for trozo in r.iter_content(chunk_size=65536):
                datos.extend(trozo)
                if len(datos) > MAX_BYTES_PDF:
                    return None

        if not bytes(datos[:5]).startswith(b"%PDF"):
            return None
        texto = extraer_texto(bytes(datos))
    except Exception:
        return None

    cache.guardar_texto(clave, texto)
    return texto


# --------------------------------------------------------------------------
# Búsqueda completa
# --------------------------------------------------------------------------
def buscar_stream(rad: Radicado, meses: int = 8, **_ignorado):
    """Genera eventos ('progreso' | 'hallazgo' | 'fin', datos)."""
    desde, hasta = rango_de_meses(meses)

    yield "progreso", {
        "mensaje": f"Buscando publicaciones del despacho entre {desde} y {hasta}…",
        "revisados": 0,
        "total": 0,
    }
    publicaciones = listar_publicaciones(rad, desde, hasta)

    if not publicaciones:
        yield "fin", {
            "total_hallazgos": 0, "desde": desde, "hasta": hasta,
            "publicaciones": 0, "documentos": 0,
        }
        return

    yield "progreso", {
        "mensaje": f"{len(publicaciones)} publicaciones; revisando sus documentos…",
        "revisados": 0,
        "total": len(publicaciones),
    }

    # Las páginas de detalle son HTML liviano: se piden todas en paralelo.
    candidatos: list[dict] = []
    total_archivos = 0
    revisados = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        tareas = {
            pool.submit(documentos_de_publicacion, p["id"]): p for p in publicaciones
        }
        for tarea in as_completed(tareas):
            pub = tareas[tarea]
            revisados += 1
            try:
                detalle = tarea.result()
            except Exception:
                detalle = {"archivos": [], "url_estado": None}

            total_archivos += len(detalle["archivos"])
            for archivo in detalle["archivos"]:
                if coincide_nombre(archivo["nombre"], rad):
                    candidatos.append({**archivo, "publicacion": pub["titulo"],
                                       "url_estado": detalle["url_estado"]})

            yield "progreso", {
                "mensaje": f"Revisando publicaciones… {revisados} de {len(publicaciones)}",
                "revisados": revisados,
                "total": len(publicaciones),
                "hallazgos": len(candidatos),
            }

    if not candidatos:
        yield "fin", {
            "total_hallazgos": 0, "desde": desde, "hasta": hasta,
            "publicaciones": len(publicaciones), "documentos": total_archivos,
        }
        return

    yield "progreso", {
        "mensaje": f"{len(candidatos)} documento(s) corresponden al radicado; leyéndolos…",
        "revisados": 0,
        "total": len(candidatos),
    }

    # Solo ahora se descargan PDFs, y únicamente los que corresponden.
    encontrados = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        tareas = {
            pool.submit(texto_documento, c["uuid"], c["url"]): c for c in candidatos
        }
        for tarea in as_completed(tareas):
            c = tareas[tarea]
            try:
                texto = tarea.result()
            except Exception:
                texto = None

            analisis = extractor.analizar(texto or "", rad) or {}
            if not analisis:
                # El nombre del archivo ya identifica el proceso aunque el PDF
                # sea una imagen escaneada sin capa de texto.
                analisis = {
                    "certeza": "por_nombre",
                    "certeza_texto": "Identificado por el nombre del archivo",
                    "decision_etiqueta": "Sin texto legible",
                    "decision": (
                        "El documento no tiene texto seleccionable (probablemente "
                        "está escaneado). Ábralo para leerlo."
                    ),
                    "resumen": "Documento escaneado: ábralo para leer la decisión.",
                    "fragmento": "",
                }

            encontrados += 1
            yield "hallazgo", {
                "titulo": c["nombre"],
                "publicacion": c["publicacion"],
                "fecha": extractor.detectar_fecha(texto or "")
                or extractor.fecha_de_titulo(c["publicacion"]),
                "url_documento": c["url"],
                "url_estado": c["url_estado"],
                # Respaldo para la ficha del caso cuando la API de Consulta de
                # Procesos no conoce el proceso: el documento mismo trae la
                # clase de proceso y las partes en su encabezado.
                "encabezado": extractor.extraer_encabezado(texto or ""),
                **analisis,
            }

    cache.podar()
    yield "fin", {
        "total_hallazgos": encontrados, "desde": desde, "hasta": hasta,
        "publicaciones": len(publicaciones), "documentos": total_archivos,
    }


def buscar(rad: Radicado, meses: int = 8, **_ignorado) -> dict:
    """Versión sin streaming, para el formulario sin JavaScript."""
    hallazgos, resumen = [], {}
    for tipo, datos in buscar_stream(rad, meses):
        if tipo == "hallazgo":
            hallazgos.append(datos)
        elif tipo == "fin":
            resumen = datos
    hallazgos.sort(key=lambda h: h.get("fecha") or "", reverse=True)
    return {"hallazgos": hallazgos, **resumen}
