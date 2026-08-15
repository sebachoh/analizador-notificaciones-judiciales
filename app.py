#!/usr/bin/env python3
"""Buscador Judicial Colombia — servidor web local.

Uso:
    pip3 install -r requirements.txt
    python3 app.py

Luego abrir http://127.0.0.1:5000
"""

from __future__ import annotations

import json
import os
import time

from flask import Flask, Response, jsonify, render_template, request

from buscador import __version__, cache, casos, consulta_procesos, portal
from buscador.radicado import RadicadoInvalido, parsear

MESES_POR_DEFECTO = int(os.environ.get("BJC_MESES", "8"))
PUERTO = int(os.environ.get("BJC_PUERTO", "5000"))

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


def _meses_solicitados() -> int:
    try:
        meses = int(request.values.get("meses", MESES_POR_DEFECTO))
    except (TypeError, ValueError):
        meses = MESES_POR_DEFECTO
    return max(1, min(meses, 36))


def _respaldo(rad, encabezado: dict) -> dict | None:
    """Ficha para `casos.py` a partir del encabezado leído de un documento.

    Se usa cuando la API de Consulta de Procesos no conoce el proceso: el
    despacho se deduce del propio radicado, y la clase/partes del documento.
    """
    if not encabezado or not (encabezado.get("sujetos") or encabezado.get("clase_proceso")):
        return None
    return {**encabezado, "despacho": rad.despacho_descripcion}


# --------------------------------------------------------------------------
# Vistas
# --------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template(
        "index.html",
        version=__version__,
        meses_defecto=MESES_POR_DEFECTO,
        casos=casos.listar(),
    )


@app.route("/buscar", methods=["POST"])
def buscar_sin_js():
    """Respaldo para navegadores sin JavaScript: una sola respuesta completa."""
    entrada = request.form.get("radicado", "")
    meses = _meses_solicitados()
    try:
        rad = parsear(entrada)
    except RadicadoInvalido as exc:
        return (
            render_template(
                "index.html",
                version=__version__,
                meses_defecto=meses,
                casos=casos.listar(),
                radicado_ingresado=entrada,
                error=str(exc),
            ),
            400,
        )

    inicio = time.perf_counter()
    expediente = consulta_procesos.expediente(rad.completo)
    resultado = portal.buscar(rad, meses=meses)
    mejor_encabezado = next(
        (h["encabezado"] for h in resultado["hallazgos"]
         if h.get("encabezado", {}).get("sujetos") or h.get("encabezado", {}).get("clase_proceso")),
        {},
    )
    casos.marcar_revisado(
        rad.formateado, len(resultado["hallazgos"]), expediente,
        _respaldo(rad, mejor_encabezado),
    )
    return render_template(
        "index.html",
        version=__version__,
        meses_defecto=meses,
        casos=casos.listar(),
        radicado_ingresado=entrada,
        desglose=rad.to_dict(),
        expediente=expediente,
        resultado=resultado,
        segundos=round(time.perf_counter() - inicio, 1),
    )


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
@app.route("/api/radicado")
def api_radicado():
    """Descompone el radicado sin consultar el portal (respuesta inmediata)."""
    try:
        rad = parsear(request.args.get("radicado", ""))
    except RadicadoInvalido as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "desglose": rad.to_dict()})


@app.route("/api/buscar")
def api_buscar():
    """Búsqueda en streaming (Server-Sent Events)."""
    entrada = request.args.get("radicado", "")
    meses = _meses_solicitados()

    try:
        rad = parsear(entrada)
    except RadicadoInvalido as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    def evento(tipo: str, datos: dict) -> str:
        return f"event: {tipo}\ndata: {json.dumps(datos, ensure_ascii=False)}\n\n"

    def flujo():
        inicio = time.perf_counter()
        yield evento("desglose", rad.to_dict())

        # La API de Consulta de Procesos responde por radicado en ~1 s, así que
        # el expediente aparece en pantalla antes de tocar el portal de
        # publicaciones, que es la parte lenta.
        try:
            expediente = consulta_procesos.expediente(rad.completo)
        except Exception:
            expediente = None
        yield evento("expediente", expediente or {"no_encontrado": True})

        mejor_encabezado: dict = {}
        try:
            for tipo, datos in portal.buscar_stream(rad, meses=meses):
                if tipo == "hallazgo":
                    enc = datos.get("encabezado") or {}
                    if enc.get("sujetos") and not mejor_encabezado.get("sujetos"):
                        mejor_encabezado = enc
                if tipo == "fin":
                    datos["segundos"] = round(time.perf_counter() - inicio, 1)
                    # Si el radicado está en «Mis casos», queda anotado cuándo
                    # se revisó y con qué resultado. Si la API no conoce el
                    # proceso, la ficha se completa con lo que trae el
                    # encabezado del documento encontrado.
                    casos.marcar_revisado(
                        rad.formateado, datos.get("total_hallazgos", 0),
                        expediente, _respaldo(rad, mejor_encabezado),
                    )
                yield evento(tipo, datos)
        except Exception as exc:  # pragma: no cover - salvaguarda de red
            yield evento("error", {"mensaje": f"No se pudo completar la consulta: {exc}"})

    return Response(
        flujo(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/expediente")
def api_expediente():
    """Identidad y actuaciones del proceso, sin tocar el portal de publicaciones."""
    try:
        rad = parsear(request.args.get("radicado", ""))
    except RadicadoInvalido as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    datos = consulta_procesos.expediente(rad.completo)
    if not datos:
        return jsonify({"ok": False, "error": "La Rama Judicial no reporta este proceso."}), 404
    return jsonify({"ok": True, "expediente": datos})


@app.route("/api/casos", methods=["GET", "POST", "DELETE"])
def api_casos():
    if request.method == "GET":
        return jsonify({"ok": True, "casos": casos.listar()})

    cuerpo = request.get_json(silent=True) or {}
    entrada = cuerpo.get("radicado", "")

    if request.method == "DELETE":
        return jsonify({"ok": True, "casos": casos.eliminar(entrada)})

    try:
        rad = parsear(entrada)
    except RadicadoInvalido as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    referencia = (cuerpo.get("referencia") or cuerpo.get("alias") or "").strip()[:80]
    # Se trae la ficha del proceso para que la lista muestre las partes sin
    # que haya que abrir cada caso. Si la API no responde, el caso igual se
    # guarda: los datos se completarán en la próxima consulta.
    expediente = consulta_procesos.expediente(rad.completo)
    return jsonify(
        {
            "ok": True,
            "casos": casos.agregar(rad.formateado, referencia, expediente),
            "sin_ficha": expediente is None,
        }
    )


@app.route("/api/version")
def api_version():
    """Sirve para comprobar de un vistazo qué versión está corriendo."""
    return jsonify({"ok": True, "version": __version__, "motor_pdf": portal.MOTOR_PDF})


@app.route("/api/cache", methods=["GET", "DELETE"])
def api_cache():
    if request.method == "DELETE":
        cache.limpiar_todo()
    return jsonify({"ok": True, "cache": cache.estadisticas()})


def _puerto_ocupado(puerto: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


if __name__ == "__main__":
    print(f"\n  ⚖️  Buscador Judicial Colombia v{__version__}")
    print(f"     Motor de PDF: {portal.MOTOR_PDF}")
    print(f"     Ventana de consulta: últimos {MESES_POR_DEFECTO} meses")
    print(f"     Caché: {cache.estadisticas()['ruta']}")

    # Un servidor viejo dejado corriendo se queda con el puerto y el navegador
    # sigue mostrando la versión anterior. Es mejor decirlo claramente que
    # fallar con un «Address already in use» que pasa desapercibido.
    if _puerto_ocupado(PUERTO):
        print(f"\n  ⚠️  El puerto {PUERTO} ya está ocupado por otro programa.")
        print("     Seguramente es una versión anterior de esta misma aplicación.")
        print("     Ciérrela con:")
        print(f"\n         lsof -ti tcp:{PUERTO} | xargs kill\n")
        print("     …y vuelva a ejecutar  python3 app.py")
        print(f"     (o use otro puerto:  BJC_PUERTO=5100 python3 app.py)\n")
        raise SystemExit(1)

    print(f"\n     Abra su navegador en:  http://127.0.0.1:{PUERTO}")
    print(f"     Para comprobar la versión:  http://127.0.0.1:{PUERTO}/api/version\n")
    app.run(host="127.0.0.1", port=PUERTO, debug=False, threaded=True)
