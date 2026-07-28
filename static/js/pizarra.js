/* El banner de juegos: flechas, el detalle al pasar el mouse, y el refresco de los juegos en vivo.
 *
 * Todo el contenido viene ya armado del servidor. Acá no se pide nada por juego ni se calcula nada:
 * solo se desplaza la tira, se saca al panel de abajo el detalle que cada tarjeta trae escondido, y
 * cada minuto se pide la tira completa de nuevo mientras haya pelota en curso.
 */
(function () {
  "use strict";

  var CADA = 60000;
  var temporizador = null;

  function banner() {
    return document.getElementById("pizarra");
  }

  /* ---------- Las flechas ---------- */

  function desplazar(tira, sentido) {
    // Poco menos que el ancho visible, para que quede a la vista una tarjeta de las que ya estaban:
    // saltar la pantalla entera hace perder el hilo de dónde se estaba.
    tira.scrollBy({ left: sentido * (tira.clientWidth * 0.8), behavior: "smooth" });
  }

  function pintarFlechas(raiz) {
    var tira = raiz.querySelector(".dgl-tira");
    var izq = raiz.querySelector(".dgl-flecha-izq");
    var der = raiz.querySelector(".dgl-flecha-der");
    if (!tira || !izq || !der) return;
    var resto = tira.scrollWidth - tira.clientWidth - tira.scrollLeft;
    izq.disabled = tira.scrollLeft <= 1;
    der.disabled = resto <= 1;
  }

  /* ---------- El detalle del hover ---------- */

  // El panel se cierra con un respiro y no en el acto: está debajo de la tarjeta, así que para
  // llegar a él —a los botones de video, por ejemplo— hay que salirse de la tarjeta primero. Sin
  // esta pausa se cerraría justo en el camino y no habría forma de hacerle clic a nada.
  var cierre = null;

  function programarCierre(raiz) {
    cierre = setTimeout(function () { ocultarDetalle(raiz); }, 200);
  }

  function cancelarCierre() {
    if (cierre) { clearTimeout(cierre); cierre = null; }
  }

  function marcarAbierta(raiz, tarjeta) {
    raiz.querySelectorAll(".dgl-con-detalle").forEach(function (otra) {
      otra.setAttribute("aria-expanded", String(otra === tarjeta));
      otra.classList.toggle("is-abierta", otra === tarjeta);
    });
  }

  function mostrarDetalle(raiz, tarjeta) {
    cancelarCierre();
    var panel = raiz.querySelector(".dgl-detalle");
    var plantilla = tarjeta.querySelector(".dgl-juego-detalle");
    if (!panel || !plantilla) return;

    panel.innerHTML = "";
    panel.appendChild(plantilla.content.cloneNode(true));
    panel.hidden = false;
    marcarAbierta(raiz, tarjeta);

    // Alineado con la tarjeta, pero sin salirse del banner por la derecha.
    var izquierda = tarjeta.getBoundingClientRect().left - raiz.getBoundingClientRect().left;
    var sobra = raiz.clientWidth - panel.offsetWidth;
    panel.style.left = Math.max(0, Math.min(izquierda, sobra)) + "px";
  }

  function ocultarDetalle(raiz) {
    var panel = raiz.querySelector(".dgl-detalle");
    if (panel) { panel.hidden = true; }
    marcarAbierta(raiz, null);
  }

  function abierta(raiz) {
    return raiz.querySelector('.dgl-con-detalle[aria-expanded="true"]');
  }

  function entrarAlPanel(raiz) {
    var panel = raiz.querySelector(".dgl-detalle");
    if (!panel || panel.hidden) return;
    // Al primer enlace o botón que haya. Si no hay ninguno —un juego sin videos ni perfiles— se
    // enfoca el panel mismo, para que el lector de pantalla lo lea y Escape tenga desde dónde volver.
    var primero = panel.querySelector('a[href], button:not([disabled])');
    if (primero) { primero.focus(); return; }
    panel.tabIndex = -1;
    panel.focus();
  }

  /* ---------- El refresco ---------- */

  function programar() {
    var raiz = banner();
    if (temporizador) { clearTimeout(temporizador); temporizador = null; }
    if (raiz && raiz.dataset.vivo === "1") {
      temporizador = setTimeout(refrescar, CADA);
    }
  }

  function refrescar() {
    var raiz = banner();
    // Con el mouse encima no se reemplaza nada: al lector se le cerraría el detalle que está leyendo.
    if (!raiz || raiz.matches(":hover")) { programar(); return; }
    var scroll = raiz.querySelector(".dgl-tira").scrollLeft;

    fetch("/pizarra/", { headers: { "X-Requested-With": "fetch" } })
      .then(function (r) { return r.ok ? r.text() : Promise.reject(r.status); })
      .then(function (html) {
        var actual = banner();
        // Sin juegos la vista devuelve vacío: se deja lo que hay en vez de borrar el banner.
        if (!actual || !html.trim()) return;
        actual.outerHTML = html;
        var nuevo = banner();
        if (nuevo) {
          // Se devuelve el desplazamiento donde estaba: si no, cada minuto la tira saltaría al inicio.
          nuevo.querySelector(".dgl-tira").scrollLeft = scroll;
          preparar(nuevo, false);
        }
      })
      .catch(function () { /* se reintenta al minuto; el marcador viejo sigue en pantalla */ })
      .finally(programar);
  }

  /* ---------- Armado ---------- */

  function preparar(raiz, inicial) {
    var tira = raiz.querySelector(".dgl-tira");
    if (!tira) return;

    raiz.querySelectorAll(".dgl-flecha").forEach(function (boton) {
      boton.addEventListener("click", function () {
        desplazar(tira, Number(boton.dataset.mover));
      });
    });
    tira.addEventListener("scroll", function () { pintarFlechas(raiz); });

    raiz.querySelectorAll(".dgl-con-detalle").forEach(function (tarjeta) {
      tarjeta.addEventListener("mouseenter", function () { mostrarDetalle(raiz, tarjeta); });
      tarjeta.addEventListener("mouseleave", function () { programarCierre(raiz); });

      // El clic sirve al dedo y al ratón, y es lo único que un teléfono puede hacer: ahí no hay
      // hover, así que sin esto el detalle era inalcanzable. Alterna, para poder cerrarlo igual que
      // se abrió.
      tarjeta.addEventListener("click", function () {
        if (tarjeta.getAttribute("aria-expanded") === "true") { ocultarDetalle(raiz); } else { mostrarDetalle(raiz, tarjeta); }
      });

      // Enter y Espacio abren Y METEN EL FOCO en el panel. No es un adorno: el panel está después de
      // las quince tarjetas en el orden del documento, así que quien tabula desde una tarjeta llega
      // a la siguiente, no a los nombres ni a los botones de video. Sin este salto el contenido
      // seguía siendo inalcanzable por teclado aunque la tarjeta ya respondiera.
      //
      // Espacio además desplaza la página, así que hay que quedarse con el evento.
      tarjeta.addEventListener("keydown", function (evento) {
        if (evento.key !== "Enter" && evento.key !== " ") return;
        evento.preventDefault();
        mostrarDetalle(raiz, tarjeta);
        entrarAlPanel(raiz);
      });

      // Al tabular se abre, igual que al pasar el mouse: es la misma promesa para el otro dispositivo.
      tarjeta.addEventListener("focus", function () { mostrarDetalle(raiz, tarjeta); });
      // Y se cierra al salir, salvo que el foco se vaya HACIA el panel — que es justo adonde va el
      // siguiente tabulador, a los nombres y a los botones de video.
      tarjeta.addEventListener("blur", function (evento) {
        var panel = raiz.querySelector(".dgl-detalle");
        if (!panel || !panel.contains(evento.relatedTarget)) programarCierre(raiz);
      });
    });

    var panel = raiz.querySelector(".dgl-detalle");
    if (panel) {
      panel.addEventListener("mouseenter", cancelarCierre);
      panel.addEventListener("mouseleave", function () { programarCierre(raiz); });
      // El foco dentro del panel lo mantiene abierto; salir de él lo cierra.
      panel.addEventListener("focusin", cancelarCierre);
      panel.addEventListener("focusout", function (evento) {
        if (!panel.contains(evento.relatedTarget)) programarCierre(raiz);
      });
    }

    // Escape cierra y devuelve el foco a la tarjeta: si el foco se quedara dentro de un panel que
    // acaba de esconderse, el siguiente tabulador saldría de la nada.
    raiz.addEventListener("keydown", function (evento) {
      if (evento.key !== "Escape") return;
      var tarjeta = abierta(raiz);
      if (!tarjeta) return;
      ocultarDetalle(raiz);
      tarjeta.focus();
    });


    if (inicial) {
      // Se abre en los juegos de hoy: lo de ayer queda a la izquierda para quien lo busque.
      var hoy = tira.querySelector("[data-hoy]");
      if (hoy) { tira.scrollLeft = hoy.offsetLeft; }
    }
    pintarFlechas(raiz);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var raiz = banner();
    // UN SOLO listener de documento, registrado acá y no dentro de `preparar()`.
    //
    // Estaba adentro, y `preparar()` se llama en CADA refresco en vivo —o sea una vez por minuto con
    // juegos en marcha— después de reemplazar el `outerHTML` del banner. Cada pasada dejaba un
    // handler global más, cerrado sobre el banner de esa versión: una hora de juegos vivos acumulaba
    // sesenta, cincuenta y nueve de ellos apuntando a nodos ya desprendidos del documento.
    //
    // No rompía la primera interacción —por eso pasó desapercibido— pero degradaba con el tiempo y
    // justo cuando hay más tráfico. Lo destapó el review v9 (DEV-01/QA-01/FE-01).
    //
    // Acá no hace falta desmontar nada: se resuelve el banner ACTUAL en cada clic, así que el
    // reemplazo del HTML deja de importar.
    document.addEventListener("click", function (evento) {
      var actual = banner();
      if (actual && !actual.contains(evento.target)) ocultarDetalle(actual);
    });

    if (raiz) { preparar(raiz, true); }
    programar();
  });
})();
