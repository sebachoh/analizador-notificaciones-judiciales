"""Caché en disco.

Dos tipos de contenido con reglas distintas:

* **Texto de PDF** — una providencia publicada no cambia nunca, así que su texto
  se guarda de forma permanente (comprimido). Esto es lo que hace que la segunda
  búsqueda sobre un mismo despacho sea casi instantánea.
* **Listados del portal** — cambian cada día hábil, así que se guardan con un
  tiempo de vida corto.

La caché se poda sola: nunca supera `MAX_MB` ni conserva entradas más viejas que
`MAX_DIAS`, eliminando primero las menos usadas recientemente.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import threading
import time
from pathlib import Path

MAX_MB = int(os.environ.get("BJC_CACHE_MAX_MB", "300"))
MAX_DIAS = int(os.environ.get("BJC_CACHE_MAX_DIAS", "120"))

_lock = threading.Lock()


def _raiz() -> Path:
    ruta = os.environ.get("BJC_CACHE_DIR")
    if ruta:
        base = Path(ruta)
    else:
        base = Path.home() / ".cache" / "buscador-judicial-colombia"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _dir(nombre: str) -> Path:
    d = _raiz() / nombre
    d.mkdir(parents=True, exist_ok=True)
    return d


def _clave(valor: str) -> str:
    return hashlib.sha1(valor.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Texto de documentos (permanente)
# --------------------------------------------------------------------------
def leer_texto(uuid: str) -> str | None:
    ruta = _dir("documentos") / f"{_clave(uuid)}.txt.gz"
    try:
        with gzip.open(ruta, "rt", encoding="utf-8") as fh:
            contenido = fh.read()
        os.utime(ruta, None)  # marca de uso reciente, para la poda LRU
        return contenido
    except (OSError, EOFError):
        return None


def existe_texto(uuid: str) -> bool:
    """Comprueba la presencia en caché sin descomprimir el contenido."""
    return (_dir("documentos") / f"{_clave(uuid)}.txt.gz").exists()


def guardar_texto(uuid: str, texto: str) -> None:
    ruta = _dir("documentos") / f"{_clave(uuid)}.txt.gz"
    temporal = ruta.with_suffix(".tmp")
    try:
        with gzip.open(temporal, "wt", encoding="utf-8") as fh:
            fh.write(texto)
        temporal.replace(ruta)  # escritura atómica
    except OSError:
        temporal.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# Listados del portal (con tiempo de vida)
# --------------------------------------------------------------------------
def leer_listado(clave: str, ttl_segundos: int) -> object | None:
    ruta = _dir("listados") / f"{_clave(clave)}.json"
    try:
        if time.time() - ruta.stat().st_mtime > ttl_segundos:
            return None
        with ruta.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def guardar_listado(clave: str, datos: object) -> None:
    ruta = _dir("listados") / f"{_clave(clave)}.json"
    temporal = ruta.with_suffix(".tmp")
    try:
        with temporal.open("w", encoding="utf-8") as fh:
            json.dump(datos, fh)
        temporal.replace(ruta)
    except OSError:
        temporal.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# Mantenimiento
# --------------------------------------------------------------------------
def estadisticas() -> dict:
    archivos = [p for p in _raiz().rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in archivos)
    return {
        "ruta": str(_raiz()),
        "documentos": len(list((_raiz() / "documentos").glob("*.txt.gz")))
        if (_raiz() / "documentos").exists()
        else 0,
        "tamano_mb": round(total / (1024 * 1024), 2),
    }


def podar() -> int:
    """Elimina entradas vencidas o excedentes. Devuelve cuántas borró."""
    with _lock:
        archivos = []
        for p in _raiz().rglob("*"):
            if p.is_file() and p.suffix != ".tmp":
                try:
                    archivos.append((p.stat().st_atime, p.stat().st_size, p))
                except OSError:
                    continue

        borrados = 0
        limite_edad = time.time() - MAX_DIAS * 86400
        vivos = []
        for atime, size, p in archivos:
            if atime < limite_edad:
                p.unlink(missing_ok=True)
                borrados += 1
            else:
                vivos.append((atime, size, p))

        # Poda por tamaño: elimina los menos usados recientemente.
        vivos.sort()  # más antiguo primero
        total = sum(s for _, s, _ in vivos)
        limite = MAX_MB * 1024 * 1024
        for _, size, p in vivos:
            if total <= limite:
                break
            p.unlink(missing_ok=True)
            total -= size
            borrados += 1
        return borrados


def limpiar_todo() -> None:
    with _lock:
        for p in _raiz().rglob("*"):
            if p.is_file():
                p.unlink(missing_ok=True)
