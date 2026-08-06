# Buscador Judicial Colombia ⚖️

Aplicación web interactiva desarrollada para **Jose Hermes** (por Sebastian y **Rio**).

## 🚀 Funcionalidades Principales

1. **Descomposición del Código Único de Radicación (23 Dígitos):**
   - Identifica Departamento, Municipio, Entidad, Especialidad, Despacho, Año y Consecutivo.
2. **Escaneo y Extracción en Tiempo Real:**
   - Consulta notificaciones electrónicas de la Rama Judicial de Colombia.
   - Extrae la fila exacta del auto y la sección **RESUELVE** (numerales PRIMERO, SEGUNDO, TERCERO...).
3. **Generación de Enlaces Oficiales:**
   - Enlace directo al documento PDF del auto individual con UUID (`get_file?uuid=...`).
4. **Diseño Accesible (Ideal para Adultos Mayores):**
   - Tipografía moderna de alta legibilidad `Plus Jakarta Sans`.
   - Controles interactivos de escala tipográfica global para toda la página (A- / Normal / A+ / Grande A++).
5. **Mensajes dinámicos de aliento para Jose Hermes.**
6. **Mis Casos Guardados:**
   - Permite guardar y gestionar una lista de radicados frecuentes para consultar de forma rápida con un solo clic.

---

## 🛠️ Requisitos e Instalación

Para ejecutar este proyecto localmente:

```bash
# 1. Instalar dependencias necesarias
pip3 install flask pypdf requests

# 2. Iniciar la aplicación
python3 app.py
```

Luego abre tu navegador en:  
👉 **`http://127.0.0.1:5000`**
