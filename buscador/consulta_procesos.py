"""Cliente de la API de Consulta de Procesos Nacional Unificada (CPNU).

A diferencia del portal de publicaciones, esta API **sí busca por número de
radicado**, así que devuelve la identidad del proceso y su historial completo de
actuaciones en una sola llamada, sin descargar ningún PDF.

Endpoints verificados contra el servicio real:

    GET /api/v2/Procesos/Consulta/NumeroRadicacion?numero=<23 dígitos>&SoloActivos=false
    GET /api/v2/Proceso/Detalle/<idProceso>
    GET /api/v2/Proceso/Actuaciones/<idProceso>?pagina=<n>
"""

from __future__ import annotations

import os
import threading

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://consultaprocesos.ramajudicial.gov.co:448/api/v2"
TIMEOUT = (6, int(os.environ.get("BJC_TIMEOUT_API", "25")))

_local = threading.local()


def sesion() -> requests.Session:
    s = getattr(_local, "sesion_api", None)
    if s is None:
        s = requests.Session()
        adaptador = HTTPAdapter(
            max_retries=Retry(
                total=2,
                backoff_factor=0.5,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=frozenset(["GET"]),
            ),
            pool_connections=4,
            pool_maxsize=8,
        )
        s.mount("https://", adaptador)
        s.headers.update({"Accept": "application/json"})
        _local.sesion_api = s
    return s


def _get(ruta: str, params: dict | None = None) -> dict | None:
    try:
        r = sesion().get(f"{BASE}{ruta}", params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError):
        return None


def consultar(radicado_digitos: str) -> dict | None:
    """Identidad del proceso, o None si la API no lo conoce o no responde."""
    datos = _get(
        "/Procesos/Consulta/NumeroRadicacion",
        {"numero": radicado_digitos, "SoloActivos": "false"},
    )
    procesos = (datos or {}).get("procesos") or []
    if not procesos:
        return None

    p = procesos[0]
    return {
        "id_proceso": p.get("idProceso"),
        "despacho": (p.get("despacho") or "").strip(),
        "departamento": (p.get("departamento") or "").strip(),
        "sujetos": (p.get("sujetosProcesales") or "").strip(),
        "fecha_radicacion": (p.get("fechaProceso") or "")[:10],
        "fecha_ultima_actuacion": (p.get("fechaUltimaActuacion") or "")[:10],
        "es_privado": bool(p.get("esPrivado")),
    }


def detalle(id_proceso: int) -> dict:
    d = _get(f"/Proceso/Detalle/{id_proceso}") or {}
    return {
        "tipo_proceso": (d.get("tipoProceso") or "").strip(),
        "clase_proceso": (d.get("claseProceso") or "").strip(),
        "subclase_proceso": (d.get("subclaseProceso") or "").strip(),
        "ponente": (d.get("ponente") or "").strip(),
        "ubicacion": (d.get("ubicacion") or "").strip(),
        "recurso": (d.get("recurso") or "").strip(),
        "despacho_codigo": (d.get("codDespachoCompleto") or "").strip(),
    }


def actuaciones(id_proceso: int, max_paginas: int = 5) -> list[dict]:
    """Historial de actuaciones, de la más reciente a la más antigua."""
    todas: list[dict] = []
    for pagina in range(1, max_paginas + 1):
        datos = _get(f"/Proceso/Actuaciones/{id_proceso}", {"pagina": pagina})
        if not datos:
            break
        lote = datos.get("actuaciones") or []
        todas.extend(
            {
                "fecha": (a.get("fechaActuacion") or "")[:10],
                "actuacion": (a.get("actuacion") or "").strip(),
                "anotacion": (a.get("anotacion") or "").strip(),
                "fecha_inicial": (a.get("fechaInicial") or "")[:10] or None,
                "fecha_final": (a.get("fechaFinal") or "")[:10] or None,
                "con_documentos": bool(a.get("conDocumentos")),
            }
            for a in lote
        )
        paginacion = datos.get("paginacion") or {}
        if pagina >= (paginacion.get("cantidadPaginas") or 1):
            break

    todas.sort(key=lambda a: a["fecha"], reverse=True)
    return todas


def expediente(radicado_digitos: str) -> dict | None:
    """Identidad + detalle + actuaciones en una sola estructura."""
    proceso = consultar(radicado_digitos)
    if not proceso:
        return None
    if proceso["id_proceso"]:
        proceso.update(detalle(proceso["id_proceso"]))
        proceso["actuaciones"] = actuaciones(proceso["id_proceso"])
    else:
        proceso["actuaciones"] = []
    return proceso
