# Buscador Judicial Colombia ⚖️

Aplicación web local para consultar estados electrónicos y notificaciones
judiciales de la Rama Judicial de Colombia a partir del número de radicado.

Desarrollada para **Jose Hermes** (por Sebastian y **Rio**).

---

## 🚀 Instalación y uso

```bash
pip3 install -r requirements.txt
python3 app.py
```

Luego abra su navegador en 👉 **http://127.0.0.1:5000**

---

## 🔎 De dónde salen los datos

La aplicación consulta **dos fuentes oficiales distintas** y las combina:

| Fuente | Qué aporta | Costo |
|---|---|---|
| **API de Consulta de Procesos** (`consultaprocesos.ramajudicial.gov.co:448`) | Identidad del proceso, partes, clase, y el historial completo de actuaciones. Busca **por radicado**. | ~1 s |
| **Portal de Publicaciones Procesales** | El PDF de la providencia notificada por estado. **No** permite buscar por radicado. | ~3-5 s |

### Cómo se encuentra el documento sin descargar cientos de PDFs

El portal de publicaciones obliga a filtrar por despacho y fechas, no por
radicado. Pero su página de detalle lista las providencias con nombres de
archivo que **contienen el año y el consecutivo del proceso**:

```
03-2026-00036 TrasladoRecurso.pdf
   └── año y consecutivo del radicado 66001-31-03-003-2026-00036-00
```

Así que la búsqueda es: listar publicaciones del despacho → pedir las páginas de
detalle en paralelo (HTML liviano) → **filtrar por nombre de archivo** →
descargar únicamente el PDF que corresponde. Para un juzgado con 10
publicaciones y 77 documentos en 8 meses, eso es una descarga de PDF en lugar de
77.

---

## 🔎 Qué hace

1. **Descompone el Código Único de Radicación (23 dígitos)** e identifica
   municipio, departamento, tipo de entidad, especialidad, despacho, año,
   consecutivo e instancia. El juzgado se muestra en cuanto termina de escribir,
   sin necesidad de buscar.
2. **Consulta las publicaciones procesales** del despacho en una ventana móvil
   de los **últimos 8 meses** (configurable desde la misma pantalla: 3, 6, 8, 12
   o 24 meses).
3. **Muestra el expediente**: partes, clase de proceso e historial completo de
   actuaciones según la Rama Judicial.
4. **Lee la providencia** que corresponde al radicado y extrae su parte
   resolutiva, con el enlace al PDF oficial.
5. **Guarda sus casos frecuentes** en el computador, como una ficha con el
   radicado, una referencia propia, el ID del proceso en la Rama Judicial,
   demandante, demandado, despacho, clase y la fecha de la última revisión.

### Niveles de certeza

| Etiqueta | Significado |
|---|---|
| 🟢 **Exacta** | Los 23 dígitos del radicado aparecen dentro del documento, sin importar guiones, espacios o saltos de línea. |
| 🟡 **Probable** | Dentro del PDF coinciden el año y el consecutivo, pero no el radicado completo. |
| 🔵 **Por nombre** | El nombre del archivo identifica el proceso, pero el PDF está escaneado y no tiene texto legible. Hay que abrirlo para leerlo. |

---

## ⚡ Cómo logra ser rápido

- **Caché permanente del texto de los PDF.** Una providencia publicada no
  cambia, así que su texto se guarda comprimido en disco. La primera consulta a
  un despacho descarga los documentos; las siguientes son casi instantáneas.
- **Filtrado por nombre de archivo antes de descargar** (ver arriba): es la
  diferencia entre bajar 1 PDF y bajar 77.
- **El expediente aparece primero.** La API responde en ~1 s, así que las partes
  y el historial se ven en pantalla mientras el portal de publicaciones sigue
  trabajando.
- **Una sola sesión HTTP** con reutilización de conexiones y reintentos con
  espera progresiva, en lugar de abrir una conexión nueva por descarga.
- **Paginación con corte temprano**: deja de pedir páginas apenas una tanda no
  aporta documentos nuevos, en vez de pedir siempre un número fijo.
- **Resultados en vivo.** La página usa Server-Sent Events, así que cada
  decisión aparece apenas se encuentra, con progreso real (no un mensaje
  genérico).
- **Los PDF se leen en memoria**, sin escribir archivos temporales, usando
  PyMuPDF, que además de ser varias veces más rápido que `pypdf` libera el GIL
  mientras trabaja, así que los hilos sí rinden. Si PyMuPDF no está instalado se
  usa `pypdf` automáticamente.

> **Si no aparece nada**, revise la fecha de la última actuación en la ficha del
> expediente. Un proceso cuya última actuación fue hace años no tiene por qué
> tener publicaciones en los últimos 8 meses: ausencia de resultados es la
> respuesta correcta, no una falla.

---

## 📁 Mis casos guardados

Cada caso se guarda como una ficha, no como un número suelto:

| Campo | De dónde sale |
|---|---|
| **Radicado** | Lo que usted escribe, normalizado a 23 dígitos |
| **Referencia** | Un nombre suyo para reconocerlo (ej. «Cobro Fiducentro») |
| **ID Rama Judicial** | `idProceso` de la API oficial |
| **Demandante / Demandado** | Partes del proceso, según la API |
| **Despacho y clase** | Juzgado y tipo de proceso |
| **Última actuación** | Fecha del último movimiento registrado |
| **Revisado por última vez** | Cuándo se consultó desde aquí y cuántas decisiones aparecieron |

Los roles se normalizan según la clase de proceso: ejecutante/ejecutado y
accionante/accionado se muestran como demandante y demandado. Los roles
adicionales (llamado en garantía, litisconsorte…) se conservan aparte.

La fecha de revisión se actualiza sola al terminar cada búsqueda. El botón
**Actualizar ficha** vuelve a consultar las partes sin correr la búsqueda de
publicaciones.

---

## ⚙️ Configuración

Todo tiene un valor por defecto razonable; se ajusta con variables de entorno.

| Variable | Por defecto | Para qué sirve |
|---|---|---|
| `BJC_PUERTO` | `5000` | Puerto del servidor local |
| `BJC_MESES` | `8` | Ventana de consulta por defecto |
| `BJC_WORKERS` | `8` | Descargas simultáneas |
| `BJC_MAX_PAGINAS` | `20` | Tope de páginas del listado |
| `BJC_TTL_DETALLE` | `604800` | Vigencia del detalle de publicaciones (7 días) |
| `BJC_TTL_LISTADO` | `1800` | Segundos de vigencia del listado en caché |
| `BJC_CACHE_MAX_MB` | `300` | Tamaño máximo de la caché |
| `BJC_CACHE_DIR` | `~/.cache/buscador-judicial-colombia` | Ubicación de la caché |
| `BJC_DATOS_DIR` | `~/.local/share/buscador-judicial-colombia` | Casos guardados |

La caché se poda sola: nunca supera el tamaño máximo ni conserva entradas sin
usar por más de 120 días. Para vaciarla a mano:
`curl -X DELETE http://127.0.0.1:5000/api/cache`

---

## 🧱 Estructura

```
app.py                    Servidor Flask y rutas
buscador/
  catalogos.py            Códigos DANE y de entidades judiciales
  radicado.py             Descomposición del radicado
  consulta_procesos.py    Cliente de la API oficial (busca por radicado)
  portal.py               Portal de publicaciones: listado, detalle y descargas
  extractor.py            Detección del radicado y de la parte resolutiva
  cache.py                Caché en disco con poda automática
  casos.py                Casos guardados
templates/index.html      Interfaz
static/                   Estilos y JavaScript
tests/                    Pruebas (no requieren red)
```

### API

| Ruta | Descripción |
|---|---|
| `GET /api/radicado?radicado=…` | Descompone el radicado, sin consultar el portal |
| `GET /api/expediente?radicado=…` | Proceso y actuaciones desde la API oficial |
| `GET /api/buscar?radicado=…&meses=8` | Búsqueda en streaming (SSE) |
| `GET POST DELETE /api/casos` | Casos guardados |
| `GET DELETE /api/cache` | Estado y limpieza de la caché |
| `POST /buscar` | Respaldo con formulario, para navegadores sin JavaScript |

---

## 🧪 Pruebas

```bash
pip3 install pytest
python3 -m pytest tests/ -q
```

Las pruebas no tocan la red: cubren la descomposición del radicado, el cálculo
de la ventana de fechas, la detección de coincidencias y falsos positivos, la
caché y los casos guardados.

---

## ♿ Accesibilidad

Pensada para lectura cómoda: tipografía `Plus Jakarta Sans`, control de tamaño
de letra que se recuerda entre visitas, botones grandes, foco visible y respeto
por la preferencia del sistema de reducir animaciones.

---

## 📌 Notas

- El municipio y el departamento se deducen del código DANE del radicado, así
  que la aplicación funciona igual para procesos de Pereira o de cualquier otra
  ciudad del país.
- Los catálogos de entidad y especialidad son parciales a propósito: cuando un
  código no está registrado se muestra el código en crudo en lugar de arriesgar
  una descripción equivocada.
- La aplicación escucha únicamente en `127.0.0.1`, es decir, solo es accesible
  desde este mismo computador.
