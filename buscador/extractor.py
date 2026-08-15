"""Análisis del texto de una publicación para decidir si menciona un radicado.

El criterio de coincidencia es lo que separa un resultado útil de un falso
positivo. La versión anterior de la aplicación buscaba el consecutivo de 5
dígitos como subcadena libre dentro de todo el PDF, lo que hacía coincidir
fechas, folios y radicados ajenos. Aquí se usan dos niveles explícitos:

* **exacta**  — los 23 dígitos del radicado aparecen consecutivos, ignorando
  guiones, espacios y saltos de línea.
* **probable** — aparecen juntos el año y el consecutivo (p. ej. "2026-00149"),
  pero no el radicado completo. Se marca como tal en la interfaz.
"""

from __future__ import annotations

import re
import unicodedata

VENTANA_ANTES = 400
VENTANA_DESPUES = 2500
MAX_RESUELVE = 3000

_ENCABEZADOS_DECISION = (
    "RESUELVE",
    "RESUELVE:",
    "SE RESUELVE",
    "DISPONE",
    "ORDENA",
    "DECIDE",
    "FALLA",
)

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

_RE_FECHA_TEXTO = re.compile(
    r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})", re.IGNORECASE
)
_RE_FECHA_NUM = re.compile(r"\b(\d{4})[-/](\d{2})[-/](\d{2})\b")
_RE_FECHA_NUM_INV = re.compile(r"\b(\d{2})[-/](\d{2})[-/](\d{4})\b")

# Resumen de la parte resolutiva: los autos y sentencias numeran sus órdenes
# (Primero, Segundo…) y la primera suele ser la sustantiva — qué se libra,
# admite u ordena —, mientras que las siguientes son de trámite (costas,
# notificaciones, recursos). Se toma esa primera para adelantar de qué trata
# la decisión antes de mostrar el texto completo.
_ORDINALES = (
    "primero", "primera", "único", "unico", "única", "unica",
    "segundo", "segunda", "tercero", "tercera", "cuarto", "cuarta",
    "quinto", "quinta", "sexto", "sexta", "séptimo", "septimo",
    "séptima", "septima", "octavo", "octava", "noveno", "novena",
    "décimo", "decimo", "décima", "decima",
)
_RE_PUNTO = re.compile(
    r"(?im)^[ \t]*(" + "|".join(_ORDINALES) + r")\b[°.\-:]*[ \t]*[-.:]?[ \t]*"
)
_RE_RUIDO_RESUMEN = re.compile(
    r"(?im)^[ \t]*(FIRMADO ELECTR[OÓ]NICAMENTE|Ley\s+\d.*|Acuerdo\s+[A-Z0-9].*)[ \t]*$\n?"
)
LARGO_RESUMEN = 260

# Autos y sentencias suelen abrir con una ficha de campo: valor. Dos formatos
# habituales según el despacho:
#   «Demandante:      CAJA DE COMPENSACIÓN FAMILIAR\nDE RISARALDA»   (en línea)
#   «Demandante\nLuis Agobardo Hincapié Vargas»                       (en tabla)
# Sirve de respaldo cuando la API de Consulta de Procesos no conoce el proceso.
_ETIQUETAS_PARTES = (
    "demandantes", "demandante", "demandadas", "demandada", "demandados", "demandado",
    "ejecutantes", "ejecutante", "ejecutadas", "ejecutada", "ejecutados", "ejecutado",
    "accionantes", "accionante", "accionadas", "accionada", "accionados", "accionado",
    "convocantes", "convocante", "convocadas", "convocada", "convocados", "convocado",
    "denunciantes", "denunciante", "denunciadas", "denunciada", "denunciados", "denunciado",
    "solicitantes", "solicitante", "vinculadas", "vinculada", "vinculados", "vinculado",
)
_RE_ETIQUETA_PARTE = re.compile(
    r"(?im)^[ \t]*(" + "|".join(_ETIQUETAS_PARTES) + r")[ \t]*:[ \t]*(.*)$"
)
_RE_ETIQUETA_SOLA = re.compile(
    r"(?im)^[ \t]*(" + "|".join(_ETIQUETAS_PARTES) + r")[ \t]*$"
)
_RE_PROCESO = re.compile(r"(?im)^[ \t]*Proceso[ \t]*:[ \t]*(.+)$")
_RE_CLASE_PROCESO_SOLA = re.compile(r"(?im)^[ \t]*Clase de proceso[ \t]*$")
MAX_CABECERA = 3000


def _sin_tildes(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def _indice_digitos(texto: str) -> tuple[str, list[int]]:
    """Devuelve los dígitos del texto y la posición original de cada uno."""
    digitos = []
    posiciones = []
    for i, ch in enumerate(texto):
        if ch.isdigit():
            digitos.append(ch)
            posiciones.append(i)
    return "".join(digitos), posiciones


def _limpiar(fragmento: str) -> str:
    lineas = [l.strip() for l in fragmento.splitlines()]
    lineas = [l for l in lineas if l]
    return "\n".join(lineas).strip()


def detectar_fecha(texto: str) -> str | None:
    """Extrae la fecha de publicación más plausible de la cabecera del documento."""
    cabecera = texto[:2500]

    m = _RE_FECHA_TEXTO.search(cabecera)
    if m:
        mes = _MESES.get(_sin_tildes(m.group(2)).lower())
        if mes:
            try:
                return f"{int(m.group(3)):04d}-{mes:02d}-{int(m.group(1)):02d}"
            except ValueError:
                pass

    m = _RE_FECHA_NUM.search(cabecera)
    if m and 1990 <= int(m.group(1)) <= 2100:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    m = _RE_FECHA_NUM_INV.search(cabecera)
    if m and 1990 <= int(m.group(3)) <= 2100:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

    return None


def fecha_de_titulo(titulo: str) -> str | None:
    """Fecha embebida en títulos como 'Estado No.063 de 10 de agosto de 2026'."""
    return detectar_fecha(titulo or "")


def detectar_titulo(texto: str, respaldo: str) -> str:
    """Toma la línea de cabecera más descriptiva (normalmente el n.º de estado)."""
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    mejor = None
    for linea in lineas[:25]:
        arriba = _sin_tildes(linea).upper()
        if any(p in arriba for p in ("ESTADO", "AUTO", "SENTENCIA", "TRASLADO", "EDICTO")):
            if 10 <= len(linea) <= 160:
                mejor = linea
                break
    return mejor or respaldo


def _extraer_decision(texto: str, inicio: int, fin: int) -> tuple[str, str]:
    """Busca la parte resolutiva, primero cerca de la coincidencia y luego global.

    Devuelve (etiqueta, contenido).
    """
    ventana_ini = max(0, inicio - VENTANA_ANTES)
    ventana_fin = min(len(texto), fin + VENTANA_DESPUES)
    ventana = texto[ventana_ini:ventana_fin]
    arriba_ventana = _sin_tildes(ventana).upper()

    for encabezado in _ENCABEZADOS_DECISION:
        pos = arriba_ventana.find(encabezado)
        if pos != -1:
            return "Parte resolutiva", _limpiar(ventana[pos : pos + MAX_RESUELVE])

    arriba_total = _sin_tildes(texto).upper()
    for encabezado in _ENCABEZADOS_DECISION:
        pos = arriba_total.find(encabezado)
        if pos != -1:
            return "Parte resolutiva del documento", _limpiar(texto[pos : pos + MAX_RESUELVE])

    return "Anotación del estado", _limpiar(ventana)


def resumir_decision(decision: str) -> str:
    """Adelanto corto de la parte resolutiva: el primer punto, recortado.

    No es un resumen generado por IA — es una extracción por reglas: toma el
    primer punto numerado (que suele ser el sustantivo) y lo recorta a
    `LARGO_RESUMEN` caracteres. Si el texto no tiene puntos numerados
    (anotaciones de estado sin «RESUELVE»), recorta el texto completo.
    """
    if not decision:
        return ""

    texto = _RE_RUIDO_RESUMEN.sub("", decision).strip()
    puntos = list(_RE_PUNTO.finditer(texto))

    if puntos:
        inicio = puntos[0].end()
        fin = puntos[1].start() if len(puntos) > 1 else len(texto)
        fragmento = texto[inicio:fin]
    else:
        fragmento = texto

    fragmento = " ".join(fragmento.split())
    if len(fragmento) <= LARGO_RESUMEN:
        return fragmento

    corte = fragmento.rfind(" ", 0, LARGO_RESUMEN)
    corte = corte if corte > 0 else LARGO_RESUMEN
    return fragmento[:corte].rstrip(",;:") + "…"


def analizar(texto: str, rad) -> dict | None:
    """Devuelve los datos de la coincidencia, o None si el documento no aplica.

    `rad` es un `buscador.radicado.Radicado`.
    """
    if not texto:
        return None

    digitos, posiciones = _indice_digitos(texto)

    # Nivel 1: los 23 dígitos completos, sin importar los separadores.
    idx = digitos.find(rad.completo)
    if idx != -1:
        inicio = posiciones[idx]
        fin = posiciones[idx + len(rad.completo) - 1] + 1
        etiqueta, contenido = _extraer_decision(texto, inicio, fin)
        return {
            "certeza": "exacta",
            "certeza_texto": "Radicado completo encontrado en el documento",
            "fragmento": _limpiar(texto[max(0, inicio - 200) : fin + 400]),
            "decision_etiqueta": etiqueta,
            "decision": contenido,
            "resumen": resumir_decision(contenido),
        }

    # Nivel 2: año + consecutivo contiguos (formato abreviado habitual).
    patron = re.compile(
        rf"(?<!\d){re.escape(rad.anio)}\s*[-–—/ ]?\s*{re.escape(rad.consecutivo)}(?!\d)"
    )
    m = patron.search(texto)
    if m:
        etiqueta, contenido = _extraer_decision(texto, m.start(), m.end())
        return {
            "certeza": "probable",
            "certeza_texto": "Coincide el año y el consecutivo, pero no el radicado completo",
            "fragmento": _limpiar(texto[max(0, m.start() - 200) : m.end() + 400]),
            "decision_etiqueta": etiqueta,
            "decision": contenido,
            "resumen": resumir_decision(contenido),
        }

    return None


def extraer_encabezado(texto: str) -> dict:
    """Ficha del proceso (clase, demandante, demandado) leída del encabezado.

    Respaldo para cuando la API de Consulta de Procesos no conoce el proceso:
    el documento mismo trae la ficha en sus primeras líneas, en uno de dos
    formatos según el despacho:

    * **en línea** — «Demandante:   CAJA DE COMPENSACIÓN FAMILIAR\\nDE
      RISARALDA», a veces partido en dos líneas cuando el valor no cabe. Se
      acepta como continuación una segunda línea solo si es corta, no trae
      ':' propio ni termina en coma o punto — para no arrastrar el párrafo
      narrativo que sigue.
    * **en tabla** — «Demandante\\nLuis Agobardo Hincapié Vargas»: la
      etiqueta sola en su línea, sin dos puntos, y el valor en la siguiente.

    Devuelve ``{"clase_proceso": ..., "sujetos": "Demandante: X | Demandado: Y"}``
    en el mismo formato que produce la API, listo para `casos.separar_sujetos`.
    """
    cabecera = texto[:MAX_CABECERA]
    lineas = [l.strip() for l in cabecera.splitlines() if l.strip()]

    partes: list[str] = []
    clase_proceso = ""
    i = 0
    while i < len(lineas):
        linea = lineas[i]
        siguiente = lineas[i + 1] if i + 1 < len(lineas) else ""

        m = _RE_ETIQUETA_PARTE.match(linea)
        if m:
            etiqueta, valor = m.group(1), m.group(2).strip()
            if (
                valor
                and siguiente
                and ":" not in siguiente[:25]
                and siguiente == siguiente.upper()
                and not siguiente.endswith((",", ".", ";", ":"))
                and len(valor) + len(siguiente) <= 70
            ):
                valor = f"{valor} {siguiente}"
                i += 1
            if valor:
                partes.append(f"{etiqueta.strip().title()}: {valor}")
            i += 1
            continue

        if _RE_ETIQUETA_SOLA.match(linea) and siguiente and not (
            _RE_ETIQUETA_SOLA.match(siguiente) or _RE_ETIQUETA_PARTE.match(siguiente)
        ):
            partes.append(f"{linea.title()}: {siguiente}")
            i += 2
            continue

        if not clase_proceso:
            mp = _RE_PROCESO.match(linea)
            if mp:
                clase_proceso = mp.group(1).strip()
                i += 1
                continue
            if _RE_CLASE_PROCESO_SOLA.match(linea) and siguiente:
                clase_proceso = siguiente
                i += 2
                continue

        i += 1

    return {"clase_proceso": clase_proceso, "sujetos": " | ".join(partes)}
