"""Pruebas de la lógica que no depende de la red."""

import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("BJC_CACHE_DIR", tempfile.mkdtemp())
os.environ.setdefault("BJC_DATOS_DIR", tempfile.mkdtemp())

import pytest  # noqa: E402

from buscador import cache, casos, extractor, portal  # noqa: E402
from buscador.radicado import RadicadoInvalido, parsear  # noqa: E402

RADICADO = "66001310300420260014900"


# --------------------------------------------------------------- radicado
def test_parsea_con_cualquier_separador():
    for texto in (
        RADICADO,
        "66001-31-03-004-2026-00149-00",
        "66001 31 03 004 2026 00149 00",
        "66001.31.03.004.2026.00149.00",
    ):
        rad = parsear(texto)
        assert rad.completo == RADICADO
        assert rad.formateado == "66001-31-03-004-2026-00149-00"


def test_descompone_los_campos():
    rad = parsear(RADICADO)
    assert rad.municipio_codigo == "66001"
    assert rad.departamento_codigo == "66"
    assert rad.entidad_codigo == "31"
    assert rad.especialidad_codigo == "03"
    assert rad.despacho_numero == "004"
    assert rad.despacho_codigo == "660013103004"
    assert rad.anio == "2026"
    assert rad.consecutivo == "00149"
    assert rad.instancia == "00"


def test_nombres_legibles_sin_ciudad_fija():
    """El municipio sale del código, no está escrito a mano en la plantilla."""
    assert parsear(RADICADO).municipio == "PEREIRA"
    assert parsear("11001310300420260014900").municipio == "BOGOTÁ D.C."
    assert parsear("05001310300420260014900").municipio == "MEDELLÍN"
    assert parsear("76001310300420260014900").departamento == "VALLE DEL CAUCA"


def test_municipio_desconocido_no_inventa_nombre():
    rad = parsear("66999310300420260014900")
    assert rad.municipio == "Municipio 66999"


@pytest.mark.parametrize("malo", ["", "123", "abc", "6600131030042026001490012"])
def test_rechaza_radicados_invalidos(malo):
    with pytest.raises(RadicadoInvalido):
        parsear(malo)


def test_rechaza_anio_imposible():
    with pytest.raises(RadicadoInvalido):
        parsear("66001310300418500014900")


# ---------------------------------------------------------------- fechas
def test_ventana_de_ocho_meses():
    desde, hasta = portal.rango_de_meses(8, hoy=date(2026, 8, 14))
    assert (desde, hasta) == ("2025-12-14", "2026-08-14")


def test_ventana_cruza_fin_de_anio():
    desde, _ = portal.rango_de_meses(12, hoy=date(2026, 3, 31))
    assert desde == "2025-03-31"


def test_ventana_ajusta_dia_inexistente():
    desde, _ = portal.rango_de_meses(1, hoy=date(2026, 3, 31))
    assert desde == "2026-02-28"


def test_ventana_no_queda_fija_en_un_anio():
    """El error de la versión anterior: rango escrito a mano para 2026."""
    _, hasta = portal.rango_de_meses(8, hoy=date(2031, 5, 2))
    assert hasta == "2031-05-02"


# -------------------------------------------------------------- extractor
def test_encuentra_radicado_con_guiones():
    texto = "ESTADO No. 045\nProceso 66001-31-03-004-2026-00149-00\nRESUELVE:\nPRIMERO: Admitir."
    r = extractor.analizar(texto, parsear(RADICADO))
    assert r["certeza"] == "exacta"
    assert "PRIMERO" in r["decision"]


def test_encuentra_radicado_partido_en_lineas():
    texto = "Radicado 66001-31-03-004-\n2026-00149-00 admite demanda."
    assert extractor.analizar(texto, parsear(RADICADO))["certeza"] == "exacta"


def test_coincidencia_probable_por_anio_y_consecutivo():
    texto = "Estado del juzgado\nExpediente 2026-00149 — se corre traslado.\nRESUELVE: ordenar."
    r = extractor.analizar(texto, parsear(RADICADO))
    assert r["certeza"] == "probable"


def test_no_confunde_un_numero_cualquiera():
    """El fallo de la versión anterior: '00149' suelto daba falso positivo."""
    texto = "Auto de 2026. Folio 001492. Valor 3.001.490 pesos. Radicado 2025-00777-00."
    assert extractor.analizar(texto, parsear(RADICADO)) is None


def test_no_confunde_consecutivo_de_otro_anio():
    texto = "Radicado 66001-31-03-004-2024-00149-00"
    assert extractor.analizar(texto, parsear(RADICADO)) is None


# --------------------------------------------- resumen de la parte resolutiva
DECISION_REAL = (
    "RESUELVE:\n"
    "Primero- Librar mandamiento de pago por la vía del proceso Ejecutivo a favor de LA\n"
    "CAJA DE COMPENSACION FAMILIAR DE RISARALDA COMFAMILIAR RISARALDA,\n"
    "identificado Nit: 891.480.000-1 en contra de EDUARDO RODRIGUEZ PUIGROS,\n"
    "identificado con el pasaporte No. PAK475187, para que dentro del término de cinco (5)\n"
    "días contado a partir de la notificación personal del presente auto, pague las siguientes\n"
    "sumas de dinero:\n"
    "FIRMADO ELECTRÓNICAMENTE\n"
    "Ley 2213 de 2022 y Acuerdo PCJA20-11632 del C.S.J.\n"
    "Factura No EI509119:\n"
    "1) Por la suma de ($530.712.200.oo) por concepto de capital\n"
    "Segundo. En el momento procesal oportuno se resolverá lo que corresponda respecto\n"
    "de las costas que ocasione esta cobranza.\n"
    "Tercero. Imprímase el trámite del proceso ejecutivo lo reglado en el artículo 422.\n"
)


def test_resumen_toma_solo_el_primer_punto():
    resumen = extractor.resumir_decision(DECISION_REAL)
    assert resumen.startswith("Librar mandamiento de pago")
    assert "Segundo" not in resumen
    assert "Tercero" not in resumen


def test_resumen_descarta_el_ruido_de_firma():
    resumen = extractor.resumir_decision(DECISION_REAL)
    assert "FIRMADO" not in resumen
    assert "Ley 2213" not in resumen


def test_resumen_se_recorta_sin_cortar_palabras():
    resumen = extractor.resumir_decision(DECISION_REAL)
    assert len(resumen) <= extractor.LARGO_RESUMEN + 1
    assert resumen.endswith("…")
    assert not resumen[:-1].endswith(" ")


def test_resumen_sin_puntos_numerados_recorta_el_texto_completo():
    texto = "Se corre traslado de la demanda a la parte demandada por el término legal."
    assert extractor.resumir_decision(texto) == texto


def test_resumen_vacio_si_no_hay_decision():
    assert extractor.resumir_decision("") == ""


def test_analizar_incluye_el_resumen():
    texto = f"Proceso 66001-31-03-004-2026-00149-00\n{DECISION_REAL}"
    r = extractor.analizar(texto, parsear(RADICADO))
    assert r["resumen"].startswith("Librar mandamiento de pago")
    assert r["resumen"] != r["decision"]


def test_detecta_fecha_en_varios_formatos():
    assert extractor.detectar_fecha("Pereira, 14 de agosto de 2026") == "2026-08-14"
    assert extractor.detectar_fecha("Fecha: 2026-08-14") == "2026-08-14"
    assert extractor.detectar_fecha("Fecha: 14/08/2026") == "2026-08-14"
    assert extractor.detectar_fecha("sin fecha aquí") is None


def test_fecha_desde_el_titulo_de_la_publicacion():
    titulo = "Notificación por Estado No.063 de 10 de agosto de 2026"
    assert extractor.fecha_de_titulo(titulo) == "2026-08-10"


# ------------------------------- encabezado del documento (ficha del proceso)
# Encabezado real de un auto que libra mandamiento de pago (JUZGADO CUARTO
# CIVIL DEL CIRCUITO DE PEREIRA, radicado 66001-31-03-004-2026-00149-00).
ENCABEZADO_REAL = (
    "RAMA JUDICIAL DEL PODER PÚBLICO\n"
    "JUZGADO CUARTO CIVIL DEL CIRCUITO DE PEREIRA\n"
    "Julio dieciséis (16) de dos mil veintiséis (2026)\n"
    "Radicación:          6600131030-04-2026-00149-00\n"
    "Proceso:                Ejecutivo Singular\n"
    "Demandante:      CAJA DE COMPENSACIÓN FAMILIAR\n"
    "DE RISARALDA\n"
    "Demandada:        EDUARDO RODRIGO PUIGROS\n"
    "CAJA DE COMPENSACIÓN FAMILIAR DE RISARALDA -COMFAMILIAR RISARALDA-,\n"
    "identificada con Nit No. 891.480.000-1, por conducto de apoderado judicial, presenta\n"
    "demanda EJECUTIVA SINGULAR contra EDUARDO RODRIGO PUIGROS.\n"
)


def test_extrae_encabezado_con_nombre_partido_en_dos_lineas():
    """El fallo real: la API no conocía el proceso, pero el PDF sí trae la ficha."""
    enc = extractor.extraer_encabezado(ENCABEZADO_REAL)
    assert enc["clase_proceso"] == "Ejecutivo Singular"
    s = casos.separar_sujetos(enc["sujetos"])
    assert s["demandante"] == "CAJA DE COMPENSACIÓN FAMILIAR DE RISARALDA"
    assert s["demandado"] == "EDUARDO RODRIGO PUIGROS"


def test_extrae_encabezado_no_arrastra_el_parrafo_siguiente():
    """La línea que sigue a 'Demandada' es el párrafo narrativo, no el nombre."""
    enc = extractor.extraer_encabezado(ENCABEZADO_REAL)
    assert "COMFAMILIAR" not in enc["sujetos"]


def test_extrae_encabezado_vacio_sin_ficha():
    assert extractor.extraer_encabezado("Traslado de la demanda a la parte accionada.") == {
        "clase_proceso": "", "sujetos": "",
    }


# Encabezado real en formato de tabla (etiqueta sola, valor en la línea
# siguiente, sin dos puntos) — JUZGADO CUARTO CIVIL MUNICIPAL DE DOSQUEBRADAS,
# radicado 66170-40-03-004-2025-00925-00.
ENCABEZADO_EN_TABLA = (
    "JUZGADO CUARTO CIVIL MUNICIPAL\n"
    "Dosquebradas, 27 de febrero de 2026\n"
    "Clase de proceso\n"
    "Ejecutivo\n"
    "Trámite o cuantía\n"
    "Menor\n"
    "Demandante\n"
    "Luis Agobardo Hincapié Vargas\n"
    "Demandado\n"
    "Carlos Augusto Villegas y Bertha Nidya Villegas de López\n"
    "Radicado\n"
    "2025-00925\n"
    "Auto\n"
    "890\n"
    "RESUELVE\n"
    "1. Seguir adelante con la ejecución.\n"
)


def test_extrae_encabezado_en_formato_de_tabla():
    """Etiqueta sola en su línea y el valor en la siguiente, sin ':'."""
    enc = extractor.extraer_encabezado(ENCABEZADO_EN_TABLA)
    assert enc["clase_proceso"] == "Ejecutivo"
    s = casos.separar_sujetos(enc["sujetos"])
    assert s["demandante"] == "Luis Agobardo Hincapié Vargas"
    assert s["demandado"] == "Carlos Augusto Villegas y Bertha Nidya Villegas de López"


def test_extrae_encabezado_en_tabla_no_confunde_radicado_con_valor():
    """'Radicado' y 'Auto' no son etiquetas de partes: no deben colarse."""
    enc = extractor.extraer_encabezado(ENCABEZADO_EN_TABLA)
    assert "2025-00925" not in enc["sujetos"]
    assert "890" not in enc["sujetos"]


def test_separa_demandada_en_femenino_como_demandado():
    """'Demandada' (grafía habitual, independiente del género de la persona)."""
    s = casos.separar_sujetos("Demandante: CAJA X | Demandada: EDUARDO RODRIGO PUIGROS")
    assert s["demandado"] == "EDUARDO RODRIGO PUIGROS"


# ------------------------------- coincidencia por nombre de archivo
# Nombres reales tomados del portal para el JUZGADO 003 CIVIL DEL CIRCUITO
# DE PEREIRA (despacho 660013103003).
NOMBRES_REALES = [
    "03-2026-00036 TrasladoRecurso.pdf",
    "02-2017-00351 AutoApruebaCostas.pdf",
    "03-2017-00028 AutoConcedeApelación.pdf",
    "03-2020-00143C4 SentenciaAnticipada.pdf",
    "03-2024-00295 AutoTieneContestadaCorreTrasladoObjecion.pdf",
    "03-2025-00324 AutoRelevaCurador.pdf",
    "03-2025-00348C2 AutoInadmiteReconvencion.pdf",
    "Traslado agosto 10.pdf",
]


def test_reconoce_el_archivo_del_radicado():
    rad = parsear("66001-31-03-003-2026-00036-00")
    coinciden = [n for n in NOMBRES_REALES if portal.coincide_nombre(n, rad)]
    assert coinciden == ["03-2026-00036 TrasladoRecurso.pdf"]


def test_reconoce_archivo_con_sufijo_de_cuaderno():
    rad = parsear("66001-31-03-003-2020-00143-00")
    assert portal.coincide_nombre("03-2020-00143C4 SentenciaAnticipada.pdf", rad)


def test_no_confunde_procesos_de_otro_anio_ni_otro_consecutivo():
    rad = parsear("66001-31-03-003-2017-00038-00")
    assert [n for n in NOMBRES_REALES if portal.coincide_nombre(n, rad)] == []


def test_no_coincide_por_prefijo_del_consecutivo():
    """'2025-00324' no debe activarse con un archivo '2025-003245'."""
    rad = parsear("66001-31-03-003-2025-00324-00")
    assert portal.coincide_nombre("03-2025-00324 AutoRelevaCurador.pdf", rad)
    assert not portal.coincide_nombre("03-2025-003245 Otro.pdf", rad)


def test_detecta_titulo_del_estado():
    texto = "RAMA JUDICIAL\nESTADO ELECTRÓNICO No. 045 DE 2026\nlistado de procesos"
    assert "ESTADO ELECTRÓNICO" in extractor.detectar_titulo(texto, "respaldo")
    assert extractor.detectar_titulo("nada relevante", "respaldo") == "respaldo"


# ------------------------------------------------------------------ caché
def test_caché_guarda_y_recupera_texto():
    cache.guardar_texto("uuid-de-prueba", "contenido del auto")
    assert cache.existe_texto("uuid-de-prueba")
    assert cache.leer_texto("uuid-de-prueba") == "contenido del auto"
    assert cache.leer_texto("uuid-inexistente") is None


def test_caché_de_listado_respeta_el_tiempo_de_vida():
    cache.guardar_listado("clave", {"a": "b"})
    assert cache.leer_listado("clave", 60) == {"a": "b"}
    assert cache.leer_listado("clave", 0) is None


# ------------------------------------------------------------------ casos
EXPEDIENTE = {
    "id_proceso": 51757971,
    "despacho": "JUZGADO 003 CIVIL DEL CIRCUITO DE PEREIRA",
    "clase_proceso": "Ejecutivo Singular",
    "sujetos": "Demandante: CENTRO COMERCIAL FIDUCENTRO P.H | Demandado: GLORIA ANDREA PATIÑO SALAZAR ",
    "fecha_ultima_actuacion": "2019-04-08",
}


@pytest.fixture(autouse=True)
def _lista_vacia():
    for c in casos.listar():
        casos.eliminar(c["radicado"])
    yield


def test_separa_demandante_y_demandado():
    s = casos.separar_sujetos(EXPEDIENTE["sujetos"])
    assert s["demandante"] == "CENTRO COMERCIAL FIDUCENTRO P.H"
    assert s["demandado"] == "GLORIA ANDREA PATIÑO SALAZAR"


def test_reconoce_roles_equivalentes():
    """Según la clase de proceso los roles cambian de nombre."""
    s = casos.separar_sujetos("Ejecutante: BANCO X | Ejecutado: JUAN PÉREZ")
    assert (s["demandante"], s["demandado"]) == ("BANCO X", "JUAN PÉREZ")

    s = casos.separar_sujetos("Accionante: MARÍA | Accionado: EPS SURA")
    assert (s["demandante"], s["demandado"]) == ("MARÍA", "EPS SURA")


def test_agrupa_varios_sujetos_del_mismo_rol():
    s = casos.separar_sujetos("Demandante: A | Demandante: B | Demandado: C")
    assert s["demandante"] == "A, B"


def test_conserva_roles_no_previstos():
    s = casos.separar_sujetos("Demandante: A | Llamado en garantía: SEGUROS Z")
    assert s["demandante"] == "A"
    assert any("SEGUROS Z" in o for o in s["otros"])


def test_sujetos_vacios_no_rompen():
    s = casos.separar_sujetos("")
    assert s == {"demandante": "", "demandado": "", "otros": []}


def test_caso_guarda_la_ficha_del_proceso():
    casos.agregar("66001-31-03-003-2017-00038-00", "Cobro Fiducentro", EXPEDIENTE)
    c = casos.listar()[0]
    assert c["referencia"] == "Cobro Fiducentro"
    assert c["id_proceso"] == 51757971
    assert c["demandante"] == "CENTRO COMERCIAL FIDUCENTRO P.H"
    assert c["demandado"] == "GLORIA ANDREA PATIÑO SALAZAR"
    assert c["fecha_ultima_actuacion"] == "2019-04-08"
    assert c["ultima_revision"] is None


def test_casos_no_se_duplican_y_conservan_la_referencia():
    casos.agregar("66001-31-03-003-2017-00038-00", "Cobro Fiducentro", EXPEDIENTE)
    casos.agregar("66001-31-03-003-2017-00038-00", "", EXPEDIENTE)
    guardados = casos.listar()
    assert len(guardados) == 1
    assert guardados[0]["referencia"] == "Cobro Fiducentro"


def test_marcar_revisado_registra_fecha_y_resultado():
    casos.agregar("66001-31-03-003-2017-00038-00", "Cobro", EXPEDIENTE)
    casos.marcar_revisado("66001-31-03-003-2017-00038-00", 0, EXPEDIENTE)
    c = casos.listar()[0]
    assert c["ultima_revision"] is not None
    assert c["ultimos_hallazgos"] == 0


def test_ficha_usa_el_respaldo_cuando_la_api_no_conoce_el_proceso():
    """El caso del radicado 2026-00149: la API no lo reporta, pero el documento sí."""
    respaldo = {
        "clase_proceso": "Ejecutivo Singular",
        "sujetos": "Demandante: CAJA DE COMPENSACIÓN FAMILIAR DE RISARALDA | "
                   "Demandada: EDUARDO RODRIGO PUIGROS",
        "despacho": "JUZGADO DE CIRCUITO 4 CIVIL de PEREIRA (RISARALDA)",
    }
    casos.agregar("66001-31-03-004-2026-00149-00", "Fiducentro 149", None, respaldo)
    c = casos.listar()[0]
    assert c["demandante"] == "CAJA DE COMPENSACIÓN FAMILIAR DE RISARALDA"
    assert c["demandado"] == "EDUARDO RODRIGO PUIGROS"
    assert c["clase_proceso"] == "Ejecutivo Singular"
    assert c["despacho"] == "JUZGADO DE CIRCUITO 4 CIVIL de PEREIRA (RISARALDA)"


def test_ficha_prefiere_la_api_sobre_el_respaldo():
    respaldo = {"clase_proceso": "Otro", "sujetos": "Demandante: X | Demandado: Y"}
    casos.agregar("66001-31-03-003-2017-00038-00", "Cobro", EXPEDIENTE, respaldo)
    c = casos.listar()[0]
    assert c["demandante"] == "CENTRO COMERCIAL FIDUCENTRO P.H"
    assert c["clase_proceso"] == "Ejecutivo Singular"


def test_marcar_revisado_ignora_casos_no_guardados():
    casos.marcar_revisado("11001-31-03-004-2026-00001-00", 3, EXPEDIENTE)
    assert casos.listar() == []


def test_caso_sin_ficha_se_guarda_igual():
    """Si la API no responde, el caso no se pierde."""
    casos.agregar("66001-31-03-003-2026-00036-00", "Sin datos", None)
    c = casos.listar()[0]
    assert c["radicado"] == "66001-31-03-003-2026-00036-00"
    assert c["demandante"] == ""


def test_migra_el_formato_antiguo(tmp_path, monkeypatch):
    """Los casos guardados por v3.0 tenían 'alias' y ningún otro dato."""
    monkeypatch.setenv("BJC_DATOS_DIR", str(tmp_path))
    (tmp_path / "casos.json").write_text(
        '[{"radicado": "66001-31-03-003-2017-00038-00", "alias": "Viejo",'
        ' "agregado": "2026-01-01T00:00:00"}]',
        encoding="utf-8",
    )
    c = casos.listar()[0]
    assert c["referencia"] == "Viejo"
    assert c["ultima_revision"] is None
    assert c["demandante"] == ""
