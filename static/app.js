/* Buscador Judicial Colombia — interfaz.
   La búsqueda usa Server-Sent Events para mostrar cada decisión en cuanto
   aparece, en vez de esperar a que termine el barrido completo. */

(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const esc = (t) => {
    const d = document.createElement("div");
    d.textContent = t == null ? "" : String(t);
    return d.innerHTML;
  };

  // ---------------------------------------------------------------- Escala
  function aplicarEscala(escala) {
    document.documentElement.style.setProperty("--escala", escala);
    try { localStorage.setItem("escalaLetra", escala); } catch (_) {}
    document.querySelectorAll(".btn-tamano").forEach((b) =>
      b.classList.toggle("activo", b.dataset.escala === String(escala))
    );
  }
  document.querySelectorAll(".btn-tamano").forEach((b) =>
    b.addEventListener("click", () => aplicarEscala(b.dataset.escala))
  );
  try { aplicarEscala(localStorage.getItem("escalaLetra") || "1"); } catch (_) {}

  // ------------------------------------------------- Vista previa del radicado
  const campoRadicado = $("radicado");
  const vistaPrevia = $("vista-previa");
  let temporizadorPrevia = null;

  async function actualizarVistaPrevia() {
    const valor = campoRadicado.value.trim();
    const digitos = valor.replace(/\D/g, "");
    if (!digitos) { vistaPrevia.hidden = true; return; }

    if (digitos.length !== 23) {
      vistaPrevia.hidden = false;
      vistaPrevia.classList.add("invalida");
      vistaPrevia.textContent = `Faltan dígitos: lleva ${digitos.length} de 23.`;
      return;
    }
    try {
      const r = await fetch(`/api/radicado?radicado=${encodeURIComponent(valor)}`);
      const d = await r.json();
      vistaPrevia.hidden = false;
      if (d.ok) {
        vistaPrevia.classList.remove("invalida");
        vistaPrevia.textContent = `✓ ${d.desglose.despacho_descripcion}`;
      } else {
        vistaPrevia.classList.add("invalida");
        vistaPrevia.textContent = d.error;
      }
    } catch (_) { vistaPrevia.hidden = true; }
  }

  campoRadicado.addEventListener("input", () => {
    clearTimeout(temporizadorPrevia);
    temporizadorPrevia = setTimeout(actualizarVistaPrevia, 250);
  });

  // ------------------------------------------------------------- Despacho
  function pintarDespacho(d) {
    $("datos-despacho").innerHTML = [
      `📌 ${d.formateado}`,
      `🏛️ ${d.entidad} ${d.despacho_numero}`,
      `📚 ${d.especialidad}`,
      `📍 ${d.ubicacion}`,
      `📅 Año ${d.anio}`,
      `⚖️ Instancia ${d.instancia}`,
    ].map((t) => `<span class="pastilla">${esc(t)}</span>`).join("");
    $("tarjeta-despacho").hidden = false;
  }

  // ------------------------------------------------------------ Expediente
  function pintarExpediente(e) {
    const caja = $("tarjeta-expediente");
    if (!e || e.no_encontrado) {
      caja.hidden = false;
      $("datos-expediente").innerHTML =
        `<p class="fs-5 mb-0 text-secondary">La Rama Judicial no reporta un proceso con
          este radicado. Puede que sea muy reciente o que el juzgado no lo haya publicado.</p>`;
      $("bloque-actuaciones").hidden = true;
      return;
    }
    caja.hidden = false;
    $("datos-expediente").innerHTML = `
      <p class="fs-5 mb-2"><strong>${esc(e.despacho)}</strong></p>
      <p class="mb-2">${esc([e.clase_proceso, e.subclase_proceso].filter(Boolean).join(" — "))}</p>
      <p class="mb-2">${esc(e.sujetos)}</p>
      <p class="text-secondary mb-0">
        Radicado el ${esc(e.fecha_radicacion)} · última actuación el ${esc(e.fecha_ultima_actuacion)}
        ${e.ubicacion ? ` · expediente en ${esc(e.ubicacion)}` : ""}
      </p>`;

    const acts = e.actuaciones || [];
    $("bloque-actuaciones").hidden = acts.length === 0;
    $("n-actuaciones").textContent = acts.length;
    $("lista-actuaciones").innerHTML = acts.map((a) => `
      <div class="actuacion">
        <span class="actuacion-fecha">${esc(a.fecha)}</span>
        <span class="actuacion-texto">${esc(a.actuacion)}${a.anotacion ? " — " + esc(a.anotacion) : ""}</span>
      </div>`).join("");
  }

  // ------------------------------------------------------------ Resultados
  let hallazgos = [];

  function tarjetaResultado(h, indice) {
    return `
      <article class="resultado" data-buscable="${esc((h.titulo + " " + h.decision).toLowerCase())}">
        <div class="d-flex justify-content-between align-items-start flex-wrap gap-2 mb-2">
          <h3 class="h5 fw-bold text-primary mb-0">${indice}. ${esc(h.titulo)}</h3>
          <span class="certeza certeza-${esc(h.certeza)}">${esc(h.certeza_texto)}</span>
        </div>
        <p class="text-secondary mb-2">
          ${h.fecha ? `📅 ${esc(h.fecha)} · ` : ""}${esc(h.publicacion || "")}
        </p>
        <div class="tarjeta-decision">
          <div class="titulo-decision">⚖️ ${esc(h.decision_etiqueta)}</div>
          <div class="contenido-decision">${esc(h.resumen || h.decision)}</div>
          ${h.decision && h.decision !== h.resumen ? `
          <details class="detalle-decision">
            <summary>Ver el texto completo</summary>
            <div class="contenido-decision-completo">${esc(h.decision)}</div>
          </details>` : ""}
        </div>
        <div class="d-flex gap-3 align-items-center flex-wrap">
          <a href="${esc(h.url_documento)}" target="_blank" rel="noopener" class="btn-pdf">
            📄 Abrir el documento PDF original
          </a>
          ${h.url_estado ? `<a href="${esc(h.url_estado)}" target="_blank" rel="noopener"
             class="enlace-alterno">Ver el estado completo del día</a>` : ""}
        </div>
      </article>`;
  }

  function repintarResultados() {
    hallazgos.sort((a, b) => {
      if (a.certeza !== b.certeza) return a.certeza === "exacta" ? -1 : 1;
      return (b.fecha || "").localeCompare(a.fecha || "");
    });
    $("lista-resultados").innerHTML = hallazgos
      .map((h, i) => tarjetaResultado(h, i + 1)).join("");
    $("contador-resultados").textContent = hallazgos.length;
    filtrar();
  }

  function filtrar() {
    const texto = ($("filtro").value || "").toLowerCase();
    document.querySelectorAll("#lista-resultados .resultado").forEach((el) => {
      el.style.display = el.dataset.buscable.includes(texto) ? "" : "none";
    });
  }
  $("filtro").addEventListener("input", filtrar);

  // -------------------------------------------------------------- Búsqueda
  let flujo = null;
  let cronometro = null;

  function detener() {
    if (flujo) { flujo.close(); flujo = null; }
    clearInterval(cronometro);
    $("tarjeta-progreso").hidden = true;
    document.querySelector(".btn-buscar").disabled = false;
  }
  $("btn-cancelar").addEventListener("click", detener);

  $("formulario").addEventListener("submit", (ev) => {
    if (typeof EventSource === "undefined") return; // sin soporte: envío normal
    ev.preventDefault();
    iniciarBusqueda();
  });

  function iniciarBusqueda() {
    const radicado = campoRadicado.value.trim();
    if (!radicado) return;

    detener();
    hallazgos = [];
    $("zona-error").innerHTML = "";
    $("lista-resultados").innerHTML = "";
    $("contador-resultados").textContent = "0";
    $("sin-resultados").hidden = true;
    $("tarjeta-resultados").hidden = false;
    $("tarjeta-progreso").hidden = false;
    document.querySelector(".btn-buscar").disabled = true;

    let segundos = 0;
    $("cronometro").textContent = "0s";
    cronometro = setInterval(() => {
      $("cronometro").textContent = ++segundos + "s";
    }, 1000);

    const parametros = new URLSearchParams({
      radicado,
      meses: $("meses").value,
    });

    flujo = new EventSource(`/api/buscar?${parametros}`);

    flujo.addEventListener("desglose", (e) => pintarDespacho(JSON.parse(e.data)));
    flujo.addEventListener("expediente", (e) => pintarExpediente(JSON.parse(e.data)));

    flujo.addEventListener("progreso", (e) => {
      const p = JSON.parse(e.data);
      $("mensaje-progreso").textContent = p.mensaje;
      const pct = p.total ? Math.round((p.revisados / p.total) * 100) : 5;
      $("barra-progreso").style.width = `${Math.max(pct, 3)}%`;
    });

    flujo.addEventListener("hallazgo", (e) => {
      hallazgos.push(JSON.parse(e.data));
      repintarResultados();
    });

    flujo.addEventListener("fin", (e) => {
      const f = JSON.parse(e.data);
      detener();
      repintarResultados();
      apiCasos("GET");  // refresca «revisado por última vez» si el caso está guardado
      $("sin-resultados").hidden = hallazgos.length > 0;
      $("titulo-resultados").innerHTML =
        `📜 Decisiones encontradas (<span id="contador-resultados">${hallazgos.length}</span>)` +
        ` <small class="text-secondary fw-normal">— ${esc(f.desde)} a ${esc(f.hasta)}: ` +
        `${esc(f.publicaciones)} publicaciones, ${esc(f.documentos)} documentos revisados ` +
        `en ${esc(f.segundos)} s</small>`;
    });

    flujo.addEventListener("error", (e) => {
      let mensaje = "Se perdió la conexión con el servidor. Intente de nuevo.";
      try { if (e.data) mensaje = JSON.parse(e.data).mensaje; } catch (_) {}
      detener();
      $("zona-error").innerHTML =
        `<div class="alert alert-danger fs-5 fw-semibold p-4">⚠️ ${esc(mensaje)}</div>`;
    });
  }

  // ---------------------------------------------------------- Casos guardados
  function fechaLegible(iso) {
    if (!iso) return null;
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    const dias = Math.floor((Date.now() - d) / 86400000);
    const cuando = d.toLocaleDateString("es-CO", { day: "2-digit", month: "short", year: "numeric" });
    if (dias <= 0) return `hoy, ${d.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" })}`;
    if (dias === 1) return "ayer";
    if (dias < 30) return `hace ${dias} días (${cuando})`;
    return cuando;
  }

  function campo(etiqueta, valor, clase) {
    if (!valor) return "";
    return `<div class="caso-campo">
              <span class="caso-etiqueta">${esc(etiqueta)}</span>
              <span class="${clase || "caso-valor"}">${esc(valor)}</span>
            </div>`;
  }

  function pintarCasos(casos) {
    $("contador-casos").textContent = casos.length;
    if (!casos.length) {
      $("lista-casos").innerHTML =
        `<div class="alert alert-light border fs-5 text-center text-muted p-4">
           Todavía no tiene casos guardados.
         </div>`;
      return;
    }
    $("lista-casos").innerHTML = casos.map((c) => {
      const revisado = fechaLegible(c.ultima_revision);
      const resultado = c.ultimos_hallazgos === null || c.ultimos_hallazgos === undefined
        ? ""
        : c.ultimos_hallazgos === 0
          ? " · sin novedades"
          : ` · ${c.ultimos_hallazgos} decisión(es)`;

      return `
      <div class="caso">
        <div class="caso-datos">
          <div class="caso-encabezado">
            <span class="caso-radicado">${esc(c.radicado)}</span>
            ${c.referencia ? `<span class="caso-referencia">${esc(c.referencia)}</span>` : ""}
          </div>
          <div class="caso-rejilla">
            ${campo("ID Rama Judicial", c.id_proceso || "no disponible", "caso-mono")}
            ${campo("Demandante", c.demandante || "—")}
            ${campo("Demandado", c.demandado || "—")}
            ${campo("Despacho", c.despacho)}
            ${campo("Clase", c.clase_proceso)}
            ${campo("Última actuación", c.fecha_ultima_actuacion)}
          </div>
          <div class="caso-revision ${revisado ? "" : "caso-revision-nunca"}">
            ${revisado
              ? `🕑 Revisado ${esc(revisado)}${esc(resultado)}`
              : "🕑 Todavía no se ha revisado"}
          </div>
        </div>
        <div class="caso-acciones">
          <button class="btn btn-primary btn-lg fw-bold px-4" data-consultar="${esc(c.radicado)}">
            🔍 Consultar
          </button>
          <button class="btn btn-outline-secondary" data-actualizar="${esc(c.radicado)}"
                  title="Actualizar los datos del proceso">🔄 Actualizar ficha</button>
          <button class="btn btn-outline-danger" data-eliminar="${esc(c.radicado)}"
                  aria-label="Eliminar caso">🗑️</button>
        </div>
      </div>`;
    }).join("");
  }

  async function apiCasos(metodo, cuerpo) {
    const opciones = { method: metodo };
    if (cuerpo) {
      opciones.headers = { "Content-Type": "application/json" };
      opciones.body = JSON.stringify(cuerpo);
    }
    const r = await fetch("/api/casos", opciones);
    const d = await r.json();
    if (!d.ok) { alert(d.error); return null; }
    pintarCasos(d.casos);
    return d.casos;
  }

  $("btn-agregar").addEventListener("click", async () => {
    const radicado = $("nuevo-radicado").value.trim();
    if (!radicado) return;
    const boton = $("btn-agregar");
    boton.disabled = true;
    boton.textContent = "Consultando…";
    try {
      const referencia = $("nueva-referencia").value.trim();
      if (await apiCasos("POST", { radicado, referencia })) {
        $("nuevo-radicado").value = "";
        $("nueva-referencia").value = "";
      }
    } finally {
      boton.disabled = false;
      boton.textContent = "➕ Agregar";
    }
  });

  $("btn-guardar").addEventListener("click", async () => {
    const radicado = campoRadicado.value.trim();
    if (!radicado) return;
    if (await apiCasos("POST", { radicado })) {
      alert("Caso guardado. Lo encontrará en la pestaña «Mis casos».");
    }
  });

  $("lista-casos").addEventListener("click", (ev) => {
    const consultar = ev.target.closest("[data-consultar]");
    if (consultar) {
      campoRadicado.value = consultar.dataset.consultar;
      document.querySelector('[data-bs-target="#panel-buscador"]').click();
      actualizarVistaPrevia();
      iniciarBusqueda();
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    const actualizar = ev.target.closest("[data-actualizar]");
    if (actualizar) {
      actualizar.disabled = true;
      actualizar.textContent = "Actualizando…";
      apiCasos("POST", { radicado: actualizar.dataset.actualizar });
      return;
    }

    const eliminar = ev.target.closest("[data-eliminar]");
    if (eliminar && confirm("¿Eliminar este caso de la lista?")) {
      apiCasos("DELETE", { radicado: eliminar.dataset.eliminar });
    }
  });

  // Migración: casos que quedaron guardados en el navegador por la versión anterior.
  async function migrarDesdeNavegador() {
    try {
      const viejos = JSON.parse(
        localStorage.getItem("misCasosGuardadosJoseHermes") ||
        localStorage.getItem("poolCasosJoseHermes") || "[]"
      );
      for (const rad of viejos) {
        await apiCasos("POST", { radicado: rad });
      }
      if (viejos.length) {
        localStorage.removeItem("misCasosGuardadosJoseHermes");
        localStorage.removeItem("poolCasosJoseHermes");
      }
    } catch (_) {}
  }

  document.addEventListener("DOMContentLoaded", async () => {
    await apiCasos("GET");
    await migrarDesdeNavegador();
    if (campoRadicado.value.trim()) actualizarVistaPrevia();
  });
})();
