import os
import re
import tempfile
import urllib.request
import urllib.parse
import json
import time
import concurrent.futures
import pypdf
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

DEPTO_MAP = {
    "05": "ANTIOQUIA", "08": "ATLÁNTICO", "11": "BOGOTÁ", "13": "BOLÍVAR",
    "15": "BOYACÁ", "17": "CALDAS", "18": "CAQUETÁ", "19": "CAUCA",
    "20": "CESAR", "23": "CÓRDOBA", "25": "CUNDINAMARCA", "27": "CHOCÓ",
    "41": "HUILA", "44": "LA GUAJIRA", "47": "MAGDALENA", "50": "META",
    "52": "NARIÑO", "54": "NORTE DE SANTANDER", "63": "QUINDÍO", "66": "RISARALDA",
    "68": "SANTANDER", "70": "SUCRE", "73": "TOLIMA", "76": "VALLE DEL CAUCA",
    "81": "ARAUCA", "85": "CASANARE", "86": "PUTUMAYO", "88": "SAN ANDRÉS",
    "91": "AMAZONAS", "94": "GUAINÍA", "95": "GUAVIARE", "97": "VAUPÉS", "99": "VICHADA"
}

ENTIDAD_MAP = {
    "31": "JUZGADO DE CIRCUITO", "33": "JUZGADO ADMINISTRATIVO",
    "40": "JUZGADO MUNICIPAL", "22": "TRIBUNAL SUPERIOR", "23": "TRIBUNAL ADMINISTRATIVO"
}

def descomponer_radicado(radicado_raw):
    rad = re.sub(r'\D', '', radicado_raw)
    if len(rad) != 23:
        raise ValueError(f"El radicado debe tener exactamente 23 dígitos. Ingresaste {len(rad)} dígitos.")
    
    depto_code = rad[0:2]
    muni_code = rad[0:5]
    entidad_id = rad[5:7]
    especialidad_id = rad[7:9]
    despacho_num = rad[9:12]
    despacho_full_code = rad[0:12]
    anio = rad[12:16]
    consecutivo = rad[16:21]
    instancia = rad[21:23]

    depto_nombre = DEPTO_MAP.get(depto_code, f"Departamento {depto_code}")
    entidad_nombre = ENTIDAD_MAP.get(entidad_id, f"Entidad {entidad_id}")

    return {
        "radicado_completo": rad,
        "radicado_formateado": f"{rad[0:5]}-{rad[5:7]}-{rad[7:9]}-{rad[9:12]}-{rad[12:16]}-{rad[16:21]}-{rad[21:23]}",
        "depto_code": depto_code,
        "depto_nombre": depto_nombre,
        "muni_code": muni_code,
        "entidad_id": entidad_id,
        "entidad_nombre": entidad_nombre,
        "especialidad_id": especialidad_id,
        "despacho_num": despacho_num,
        "despacho_full_code": despacho_full_code,
        "anio": anio,
        "consecutivo": consecutivo,
        "instancia": instancia
    }

def fetch_url_with_retry(url, retries=3, backoff=1.0):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})
            return urllib.request.urlopen(req, timeout=12).read()
        except Exception as e:
            if i == retries - 1:
                raise e
            time.sleep(backoff * (i + 1))

def escaneo_directo_publicaciones(desglose):
    base_url = 'https://publicacionesprocesales.ramajudicial.gov.co/web/publicaciones-procesales/inicio'
    
    params_niveles = [
        {
            'p_p_id': 'co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq',
            'p_p_lifecycle': '0',
            'p_p_state': 'normal',
            'p_p_mode': 'view',
            '_co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq_action': 'busqueda',
            '_co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq_fechaInicio': '2026-01-01',
            '_co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq_fechaFin': '2026-12-31',
            '_co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq_idDepto': desglose["depto_code"],
            '_co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq_idEntidad': desglose["entidad_id"],
            '_co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq_idEspecialidad': desglose["especialidad_id"],
            '_co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq_idDespacho': desglose["despacho_full_code"]
        },
        {
            'p_p_id': 'co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq',
            'p_p_lifecycle': '0',
            'p_p_state': 'normal',
            'p_p_mode': 'view',
            '_co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq_action': 'busqueda',
            '_co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq_fechaInicio': '2026-01-01',
            '_co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq_fechaFin': '2026-12-31',
            '_co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq_idDepto': desglose["depto_code"],
            '_co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq_idEntidad': desglose["entidad_id"]
        }
    ]

    pdf_dict = {}

    def fetch_page(page_url):
        try:
            html_bytes = fetch_url_with_retry(page_url, retries=3)
            html = html_bytes.decode('utf-8', errors='ignore')
            urls = re.findall(r'/documents/6098902/[^\s"\\]+', html)
            found_pdfs = {}
            for u in urls:
                clean_link = u.replace(r'\x3d', '=').replace('\\', '')
                full_link = f"https://publicacionesprocesales.ramajudicial.gov.co{clean_link}"
                found_pdfs[full_link] = "Notificación por Estado / Publicación Procesal"
            return found_pdfs
        except Exception as e:
            print(f"Advertencia en página: {e}")
            return {}

    page_urls = []
    for params in params_niveles:
        for page in range(1, 7):
            p = params.copy()
            p['_co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq_cur'] = str(page)
            page_urls.append(f"{base_url}?{urllib.parse.urlencode(p)}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = executor.map(fetch_page, page_urls)
        for res in results:
            pdf_dict.update(res)

    hallazgos = []
    consecutivo_target = desglose["consecutivo"]
    anio_target = desglose["anio"]
    
    def process_pdf(pdf_item):
        full_pdf_url, titulo_pub = pdf_item
        try:
            content = fetch_url_with_retry(full_pdf_url, retries=3)
            
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            reader = pypdf.PdfReader(tmp_path)
            pdf_text = ""
            for p in reader.pages:
                pdf_text += p.extract_text() + "\n"
            
            os.remove(tmp_path)
            
            if consecutivo_target in pdf_text or f"{anio_target}-{consecutivo_target}" in pdf_text:
                lines = [l.strip() for l in pdf_text.split('\n') if l.strip()]
                
                titulo_real = titulo_pub
                for l in lines[:10]:
                    if "ESTADO" in l.upper() or "NO." in l.upper():
                        titulo_real = l
                        break

                providencia_lineas = []
                for i, line in enumerate(lines):
                    if consecutivo_target in line:
                        start = max(0, i-1)
                        end = min(len(lines), i+4)
                        providencia_lineas.append("\n".join(lines[start:end]))
                
                resuelve_texto = ""
                if "RESUELVE" in pdf_text:
                    pos = pdf_text.find("RESUELVE")
                    resuelve_texto = pdf_text[pos:pos+1500]
                else:
                    resuelve_texto = "\n---\n".join(providencia_lineas)

                get_file_url = None
                uuid_match = re.search(r'/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', full_pdf_url)
                if uuid_match:
                    get_file_url = f"https://publicacionesprocesales.ramajudicial.gov.co/c/document_library/get_file?uuid={uuid_match.group(1)}&groupId=6098902"
                else:
                    get_file_url = full_pdf_url

                return {
                    "titulo_publicacion": titulo_real,
                    "pdf_url": full_pdf_url,
                    "get_file_url": get_file_url,
                    "resuelve_texto": resuelve_texto,
                    "texto_completo_pdf": pdf_text
                }
        except Exception as e:
            print(f"Error procesando PDF {full_pdf_url}: {e}")
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        pdf_results = executor.map(process_pdf, pdf_dict.items())
        for res in pdf_results:
            if res:
                hallazgos.append(res)

    return hallazgos

HTML_ACCESSIBLE_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Consulta Judicial - Jose Hermes</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --font-scale: 1;
        }
        html {
            font-size: calc(16px * var(--font-scale)) !important;
            transition: font-size 0.15s ease-in-out;
        }
        body {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: #f8fafc;
            color: #0f172a;
            line-height: 1.6;
            min-height: 100vh;
            padding-bottom: 80px;
        }
        
        .accessibility-bar {
            background-color: #0f172a;
            color: #ffffff;
            padding: 14px 0;
            border-bottom: 4px solid #0284c7;
        }
        .btn-text-size {
            background-color: #334155;
            color: #ffffff;
            border: 2px solid #64748b;
            font-weight: 700;
            padding: 6px 16px;
            border-radius: 8px;
            font-size: 0.95rem;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .btn-text-size:hover, .btn-text-size.active {
            background-color: #0284c7;
            border-color: #38bdf8;
        }

        .nav-tab-custom {
            font-weight: 700;
            font-size: 1.15rem;
            padding: 12px 24px;
            border-radius: 12px 12px 0 0 !important;
        }

        .card-accessible {
            background-color: #ffffff;
            border: 2px solid #cbd5e1;
            border-radius: 0 16px 16px 16px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            padding: 32px;
            margin-bottom: 30px;
        }

        .input-large {
            font-size: 1.3rem;
            padding: 16px 20px;
            border: 3px solid #94a3b8;
            border-radius: 12px;
            font-weight: 500;
        }
        .input-large:focus {
            border-color: #0284c7;
            box-shadow: 0 0 0 4px rgba(2, 132, 199, 0.25);
        }

        .btn-search-large {
            background-color: #0284c7;
            color: #ffffff;
            font-size: 1.25rem;
            font-weight: 700;
            padding: 16px 32px;
            border-radius: 12px;
            border: none;
            transition: all 0.2s ease;
        }
        .btn-search-large:hover {
            background-color: #0369a1;
            transform: scale(1.02);
        }

        .info-pill {
            background-color: #e0f2fe;
            color: #0369a1;
            border: 2px solid #7dd3fc;
            font-size: 1.05rem;
            font-weight: 600;
            padding: 10px 18px;
            border-radius: 10px;
            display: inline-block;
            margin-right: 10px;
            margin-bottom: 10px;
        }

        .resuelve-card {
            background-color: #fefce8;
            border: 3px solid #eab308;
            border-radius: 16px;
            padding: 28px;
            margin-bottom: 24px;
        }
        .resuelve-title {
            color: #854d0e;
            font-size: 1.3rem;
            font-weight: 700;
            border-bottom: 2px dashed #fde047;
            padding-bottom: 10px;
            margin-bottom: 16px;
        }
        .resuelve-content {
            color: #1c1917;
            font-size: 1.2rem;
            line-height: 1.7;
            white-space: pre-wrap;
        }

        .btn-pdf-main {
            background-color: #15803d;
            color: #ffffff;
            font-size: 1.2rem;
            font-weight: 700;
            padding: 16px 28px;
            border-radius: 12px;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 10px;
            box-shadow: 0 4px 10px rgba(21, 128, 61, 0.3);
        }
        .btn-pdf-main:hover {
            background-color: #166534;
            color: #ffffff;
            transform: scale(1.02);
        }

        /* Pantalla de carga dinámica con contador */
        #loadingOverlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(255, 255, 255, 0.96);
            z-index: 9999;
        }
        .spinner-center {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
            width: 90%;
            max-width: 600px;
        }
        .loading-header-flex {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 20px;
            margin-bottom: 20px;
        }
        .timer-badge {
            font-size: 2rem;
            font-weight: 800;
            color: #0284c7;
            background-color: #e0f2fe;
            padding: 10px 24px;
            border-radius: 50px;
            border: 3px solid #38bdf8;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            line-height: 1;
            margin: 0;
        }
        .dynamic-msg {
            font-size: 1.4rem;
            font-weight: 700;
            color: #0369a1;
            margin-top: 15px;
            min-height: 50px;
        }
    </style>
</head>
<body>

    <div class="accessibility-bar mb-4">
        <div class="container d-flex justify-content-between align-items-center">
            <span class="fw-bold fs-4">⚖️ Asistente Judicial de Jose Hermes</span>
            <div>
                <span class="me-2 fw-semibold">Tamaño Letra:</span>
                <button class="btn-text-size" onclick="changeFontSize(0.85)">A-</button>
                <button class="btn-text-size" onclick="changeFontSize(1.0)">Normal</button>
                <button class="btn-text-size" onclick="changeFontSize(1.2)">A+</button>
                <button class="btn-text-size" onclick="changeFontSize(1.4)">Grande A++</button>
            </div>
        </div>
    </div>

    <!-- Feedback de Carga Interactivo con Contador y Mensajes para Jose Hermes -->
    <div id="loadingOverlay">
        <div class="spinner-center">
            <div class="loading-header-flex">
                <div class="spinner-border text-primary" style="width: 4.5rem; height: 4.5rem; border-width: 0.35em;" role="status"></div>
                <div class="timer-badge" id="timerSeconds">0s</div>
            </div>
            <div class="dynamic-msg" id="dynamicMessage">¡Iniciando búsqueda para Jose Hermes!...</div>
            <p class="fs-5 text-secondary mt-2">Estamos revisando las notificaciones y extrayendo los autos.<br>Por favor aguarde un momento.</p>
        </div>
    </div>

    <div class="container">
        <div class="row justify-content-center">
            <div class="{% if desglose %}col-lg-8{% else %}col-lg-10{% endif %}">

                <!-- Pestañas Superiores: Buscador vs Mis Casos Guardados -->
                <ul class="nav nav-tabs border-bottom-0" id="mainTab" role="tablist">
                    <li class="nav-item" role="presentation">
                        <button class="nav-link active nav-tab-custom" id="search-tab" data-bs-toggle="tab" data-bs-target="#search-panel" type="button" role="tab">
                            🔍 Buscador de Radicado
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link nav-tab-custom" id="saved-tab" data-bs-toggle="tab" data-bs-target="#saved-panel" type="button" role="tab">
                            📁 Mis Casos Guardados (<span id="savedCount">0</span>)
                        </button>
                    </li>
                </ul>

                <div class="tab-content" id="mainTabContent">
                    
                    <!-- Pestaña 1: BUSCADOR -->
                    <div class="tab-pane fade show active" id="search-panel" role="tabpanel">
                        <div class="card-accessible">
                            <h2 class="fw-bold text-primary mb-3">¡Bienvenido Jose Hermes!</h2>
                            <p class="fs-5 text-secondary mb-4">Ingrese el número de radicado del caso (23 dígitos). El sistema buscará el juzgado y le mostrará el **RESUELVE** y el enlace al PDF original.</p>

                            <form id="searchForm" action="/buscar" method="POST" onsubmit="iniciarCargandoDinamico()">
                                <div class="mb-4">
                                    <label for="radicado" class="form-label fw-bold fs-4">Número de Radicado:</label>
                                    <input type="text" class="form-control input-large" id="radicado" name="radicado" placeholder="Ejemplo: 66001-31-03-004-2026-00149-00" required value="{{ radicado_ingresado or '' }}">
                                </div>

                                <div class="d-flex gap-3">
                                    <button type="submit" class="btn btn-search-large flex-grow-1">
                                        🔍 BUSCAR AUTO Y LEER EL RESUELVE
                                    </button>
                                    <button type="button" class="btn btn-outline-success btn-lg fw-bold" onclick="guardarRadicadoActual()">
                                        ⭐ Guardar en Mis Casos
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>

                    <!-- Pestaña 2: MIS CASOS GUARDADOS -->
                    <div class="tab-pane fade" id="saved-panel" role="tabpanel">
                        <div class="card-accessible">
                            <h2 class="fw-bold text-primary mb-3">📁 Mis Casos Guardados</h2>
                            <p class="fs-5 text-secondary mb-4">Guarde aquí los radicados que consulta con frecuencia para buscarlos con un solo clic sin tener que escribirlos nuevamente.</p>

                            <div class="input-group mb-4">
                                <input type="text" class="form-control input-large" id="newRadicadoSaved" placeholder="Agregar nuevo radicado (23 dígitos)...">
                                <button class="btn btn-success fw-bold fs-5 px-4" onclick="agregarRadicadoGuardado()">
                                    ➕ Agregar a Mis Casos
                                </button>
                            </div>

                            <div id="savedContainer" class="list-group">
                                <!-- Se llena dinámicamente con JS -->
                            </div>
                        </div>
                    </div>

                </div>

            </div>
            
            {% if desglose %}
            <div class="col-lg-4">
                <div class="card-accessible h-100">
                    <h3 class="fw-bold text-primary mb-3">📍 Datos del Juzgado y Proceso</h3>
                    <div class="d-flex flex-column gap-3">
                        <span class="info-pill">📌 Radicado: {{ desglose.radicado_formateado }}</span>
                        <span class="info-pill">🏛️ {{ desglose.entidad_nombre }} {{ desglose.despacho_num }}</span>
                        <span class="info-pill">📍 {{ desglose.depto_nombre }} - Pereira</span>
                        <span class="info-pill">📅 Año: {{ desglose.anio }}</span>
                    </div>
                </div>
            </div>
            {% endif %}
        </div>

        {% if error %}
        <div class="row justify-content-center">
            <div class="col-lg-10">
                <div class="alert alert-danger p-4 rounded-3 fs-5 fw-semibold">
                    ⚠️ <strong>Atención:</strong> {{ error }}
                </div>
            </div>
        </div>
        {% endif %}

        {% if desglose %}
        <div class="row justify-content-center mt-4">
            <div class="col-lg-12">
                <div class="card-accessible">
                    <div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-3">
                        <h3 class="fw-bold text-dark mb-0">📜 Decisiones Notificadas en 2026</h3>
                        <input type="text" id="filterDecision" class="form-control" style="max-width: 300px;" placeholder="Filtrar por tipo (ej. AUTO)..." onkeyup="filtrarDecisiones()">
                    </div>

                    {% if hallazgos %}
                        {% for item in hallazgos %}
                        <div class="mb-5 border-bottom pb-4 decision-item">
                            <h4 class="fw-bold text-primary mb-3 decision-title">#{{ loop.index }}. {{ item.titulo_publicacion }}</h4>

                            <div class="resuelve-card">
                                <div class="resuelve-title">
                                    ⚖️ SECCIÓN DEL RESUELVE (TEXTO DEL AUTO)
                                </div>
                                <div class="resuelve-content">{{ item.resuelve_texto }}</div>
                            </div>

                            {% if item.get_file_url %}
                            <div class="mb-4">
                                <a href="{{ item.get_file_url }}" target="_blank" class="btn-pdf-main">
                                    📄 ABRIR DOCUMENTO PDF ORIGINAL DEL AUTO
                                </a>
                            </div>
                            {% endif %}

                            <div class="p-3 bg-light rounded-3 border">
                                <span class="fw-bold">Enlace web oficial del archivo:</span><br>
                                <a href="{{ item.get_file_url }}" target="_blank" class="text-break">{{ item.get_file_url }}</a>
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <div class="alert alert-warning p-4 fs-5 fw-semibold mb-0">
                            No se encontraron notificaciones o providencias registradas para este número de radicado en lo transcurrido del año 2026.
                        </div>
                    {% endif %}
                </div>
            </div>
        </div>
        {% endif %}
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // --- FILTRO DE DECISIONES ---
        function filtrarDecisiones() {
            const input = document.getElementById('filterDecision').value.toUpperCase();
            const items = document.querySelectorAll('.decision-item');
            items.forEach(item => {
                const title = item.querySelector('.decision-title').innerText.toUpperCase();
                if (title.includes(input)) {
                    item.style.display = '';
                } else {
                    item.style.display = 'none';
                }
            });
        }

        // --- MENSAJES DINÁMICOS PARA JOSE HERMES ---
        const mensajesDinamicos = [
            "¡Iniciando búsqueda para Jose Hermes!...",
            "Revisando los estados del juzgado...",
            "¡Un momento Jose Hermes, ya casi lo tenemos!...",
            "Escaneando el texto de las providencias...",
            "¡Ya casi! Extrayendo el RESUELVE del documento...",
            "¡Unos segundos más Jose Hermes, casi listo!...",
            "Conectando con el servidor oficial..."
        ];

        let seconds = 0;
        let timerInterval = null;

        function iniciarCargandoDinamico() {
            document.getElementById('loadingOverlay').style.display = 'block';
            seconds = 0;
            document.getElementById('timerSeconds').innerText = '0s';
            
            timerInterval = setInterval(() => {
                seconds++;
                document.getElementById('timerSeconds').innerText = seconds + 's';
                
                if (seconds % 6 === 0) {
                    const msgAleatorio = mensajesDinamicos[Math.floor(Math.random() * mensajesDinamicos.length)];
                    document.getElementById('dynamicMessage').innerText = msgAleatorio;
                }
            }, 1000);
        }

        // ESCALA TIPOGRÁFICA GLOBAL PARA TODA LA PÁGINA
        function changeFontSize(scale) {
            document.documentElement.style.setProperty('--font-scale', scale);
            localStorage.setItem('userFontScale', scale);
        }

        const savedScale = localStorage.getItem('userFontScale');
        if (savedScale) {
            changeFontSize(savedScale);
        }

        // --- MIS CASOS GUARDADOS (LOCALSTORAGE) ---
        function getSavedRadicados() {
            const data = localStorage.getItem('misCasosGuardadosJoseHermes') || localStorage.getItem('poolCasosJoseHermes') || '[]';
            return JSON.parse(data);
        }

        function renderSavedCasos() {
            const casos = getSavedRadicados();
            document.getElementById('savedCount').innerText = casos.length;
            const container = document.getElementById('savedContainer');
            
            if (casos.length === 0) {
                container.innerHTML = '<div class="alert alert-light text-muted border fs-5 p-4 text-center">No tiene casos guardados aún, Jose Hermes. Guarde sus radicados frecuentes aquí.</div>';
                return;
            }

            let html = '';
            casos.forEach((rad, index) => {
                html += `
                <div class="list-group-item d-flex justify-content-between align-items-center p-3 mb-2 border rounded-3 bg-white shadow-sm">
                    <div>
                        <span class="fs-4 fw-bold text-primary font-monospace">${rad}</span>
                    </div>
                    <div class="d-flex gap-2">
                        <button class="btn btn-primary btn-lg fw-bold px-4" onclick="buscarDesdeGuardados('${rad}')">
                            🔍 Consultar Este Caso
                        </button>
                        <button class="btn btn-outline-danger btn-lg" onclick="eliminarRadicadoGuardado(${index})">
                            🗑️
                        </button>
                    </div>
                </div>
                `;
            });
            container.innerHTML = html;
        }

        function agregarRadicadoGuardado() {
            const input = document.getElementById('newRadicadoSaved');
            const rad = input.value.trim();
            if (!rad) return;
            
            const casos = getSavedRadicados();
            if (!casos.includes(rad)) {
                casos.push(rad);
                localStorage.setItem('misCasosGuardadosJoseHermes', JSON.stringify(casos));
                renderSavedCasos();
                input.value = '';
            }
        }

        function guardarRadicadoActual() {
            const rad = document.getElementById('radicado').value.trim();
            if (!rad) return;
            const casos = getSavedRadicados();
            if (!casos.includes(rad)) {
                casos.push(rad);
                localStorage.setItem('misCasosGuardadosJoseHermes', JSON.stringify(casos));
                renderSavedCasos();
                alert('¡Radicado guardado en Mis Casos para Jose Hermes!');
            }
        }

        function eliminarRadicadoGuardado(index) {
            const casos = getSavedRadicados();
            casos.splice(index, 1);
            localStorage.setItem('misCasosGuardadosJoseHermes', JSON.stringify(casos));
            renderSavedCasos();
        }

        function buscarDesdeGuardados(rad) {
            document.getElementById('radicado').value = rad;
            document.getElementById('search-tab').click();
            document.getElementById('searchForm').submit();
            iniciarCargandoDinamico();
        }

        document.addEventListener('DOMContentLoaded', renderSavedCasos);
    </script>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_ACCESSIBLE_TEMPLATE)

@app.route("/buscar", methods=["POST"])
def buscar():
    radicado_input = request.form.get("radicado", "")
    try:
        desglose = descomponer_radicado(radicado_input)
        hallazgos = escaneo_directo_publicaciones(desglose)
        
        return render_template_string(
            HTML_ACCESSIBLE_TEMPLATE,
            radicado_ingresado=radicado_input,
            desglose=desglose,
            hallazgos=hallazgos
        )
    except Exception as e:
        return render_template_string(
            HTML_ACCESSIBLE_TEMPLATE,
            radicado_ingresado=radicado_input,
            error=str(e)
        )

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False)
