"""Casos guardados, persistidos en el disco del usuario.

Cada caso guarda no solo el número de radicado sino la ficha del proceso —
partes, despacho, clase — para que la lista se pueda leer de un vistazo sin
tener que buscar uno por uno. Los datos se toman de la API de Consulta de
Procesos al guardar el caso y se refrescan cada vez que se consulta.

La fuente de verdad es un archivo JSON local, no el navegador.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

_lock = threading.Lock()

# Roles equivalentes según el tipo de proceso: se muestra el primero que exista.
# Los roles pasivos se escriben casi siempre en femenino («la parte
# demandada»), sin importar el género de la persona, así que se aceptan
# ambas formas.
_ROLES_ACTIVOS = ("demandante", "ejecutante", "accionante", "convocante",
                  "denunciante", "solicitante", "demandantes")
_ROLES_PASIVOS = ("demandado", "demandada", "ejecutado", "ejecutada",
                  "accionado", "accionada", "convocado", "convocada",
                  "denunciado", "denunciada", "vinculado", "vinculada",
                  "demandados", "demandadas")


def _archivo() -> Path:
    ruta = os.environ.get("BJC_DATOS_DIR")
    base = Path(ruta) if ruta else Path.home() / ".local" / "share" / "buscador-judicial-colombia"
    base.mkdir(parents=True, exist_ok=True)
    return base / "casos.json"


def separar_sujetos(texto: str) -> dict:
    """Convierte 'Demandante: X | Demandado: Y' en partes identificables.

    Devuelve ``{"demandante": ..., "demandado": ..., "otros": [...]}``. Los
    nombres de rol varían según la clase de proceso (ejecutante/ejecutado,
    accionante/accionado…), así que se normalizan a los dos roles principales.
    """
    roles: dict[str, list[str]] = {}
    for parte in (texto or "").split("|"):
        parte = parte.strip()
        if not parte:
            continue
        if ":" in parte:
            rol, nombre = parte.split(":", 1)
            roles.setdefault(rol.strip().lower(), []).append(nombre.strip())
        else:
            roles.setdefault("otros", []).append(parte)

    def primero(candidatos: tuple[str, ...]) -> str:
        for rol in candidatos:
            if roles.get(rol):
                return ", ".join(n for n in roles[rol] if n)
        return ""

    usados = set(_ROLES_ACTIVOS) | set(_ROLES_PASIVOS)
    otros = [
        f"{rol.title()}: {', '.join(nombres)}"
        for rol, nombres in roles.items()
        if rol not in usados and rol != "otros"
    ]
    otros += roles.get("otros", [])

    return {
        "demandante": primero(_ROLES_ACTIVOS),
        "demandado": primero(_ROLES_PASIVOS),
        "otros": otros,
    }


def _ficha(expediente: dict | None, respaldo: dict | None = None) -> dict:
    """Campos que se guardan en la lista a partir del expediente de la API.

    `respaldo` es la ficha leída del encabezado de un documento
    (`extractor.extraer_encabezado`): cuando la API no conoce el proceso, o
    no trae las partes, se completa con lo que ya trae la providencia
    encontrada en el portal.
    """
    expediente = expediente or {}
    respaldo = respaldo or {}
    if not expediente and not respaldo:
        return {}
    sujetos = separar_sujetos(expediente.get("sujetos") or respaldo.get("sujetos", ""))
    return {
        "id_proceso": expediente.get("id_proceso"),
        "despacho": expediente.get("despacho") or respaldo.get("despacho", ""),
        "clase_proceso": expediente.get("clase_proceso") or respaldo.get("clase_proceso", ""),
        "demandante": sujetos["demandante"],
        "demandado": sujetos["demandado"],
        "otras_partes": sujetos["otros"],
        "fecha_ultima_actuacion": expediente.get("fecha_ultima_actuacion", ""),
    }


def _normalizar(caso: dict) -> dict:
    """Completa un registro guardado por una versión anterior."""
    base = {
        "radicado": "", "referencia": "", "id_proceso": None, "despacho": "",
        "clase_proceso": "", "demandante": "", "demandado": "", "otras_partes": [],
        "fecha_ultima_actuacion": "", "agregado": "", "ultima_revision": None,
        "ultimos_hallazgos": None,
    }
    base.update({k: v for k, v in caso.items() if k in base})
    if not base["referencia"] and caso.get("alias"):
        base["referencia"] = caso["alias"]  # nombre del campo antes de v3.1
    return base


def listar() -> list[dict]:
    try:
        with _archivo().open("r", encoding="utf-8") as fh:
            datos = json.load(fh)
    except (OSError, ValueError):
        return []
    if not isinstance(datos, list):
        return []
    return [_normalizar(c) for c in datos if isinstance(c, dict)]


def _escribir(casos: list[dict]) -> None:
    destino = _archivo()
    temporal = destino.with_suffix(".tmp")
    try:
        with temporal.open("w", encoding="utf-8") as fh:
            json.dump(casos, fh, ensure_ascii=False, indent=2)
        temporal.replace(destino)
    except OSError:
        temporal.unlink(missing_ok=True)


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def agregar(radicado: str, referencia: str = "", expediente: dict | None = None,
            respaldo: dict | None = None) -> list[dict]:
    with _lock:
        casos = listar()
        ficha = _ficha(expediente, respaldo)

        for c in casos:
            if c["radicado"] == radicado:
                if referencia:
                    c["referencia"] = referencia
                c.update(ficha)
                _escribir(casos)
                return casos

        casos.append(
            _normalizar(
                {"radicado": radicado, "referencia": referencia,
                 "agregado": _ahora(), **ficha}
            )
        )
        _escribir(casos)
        return casos


def eliminar(radicado: str) -> list[dict]:
    with _lock:
        casos = [c for c in listar() if c["radicado"] != radicado]
        _escribir(casos)
        return casos


def marcar_revisado(radicado: str, hallazgos: int, expediente: dict | None = None,
                     respaldo: dict | None = None) -> None:
    """Registra que el caso se acaba de consultar y refresca su ficha.

    Silencioso a propósito: se llama al terminar cada búsqueda y no debe
    interrumpirla si el caso no está guardado.
    """
    with _lock:
        casos = listar()
        for c in casos:
            if c["radicado"] == radicado:
                c["ultima_revision"] = _ahora()
                c["ultimos_hallazgos"] = hallazgos
                c.update(_ficha(expediente, respaldo))
                _escribir(casos)
                return
