/* La ventana emergente del video.
 *
 * El manejador está en el documento y no en cada botón a propósito: los botones de la pizarra viven
 * dentro de un panel que el JS clona cada vez que se pasa el mouse, y que además se reemplaza entero
 * cada minuto con el refresco. Engancharlos uno por uno sería reengancharlos a cada rato.
 *
 * La ventana se arma sola la primera vez y se reutiliza. Al cerrarla se le quita el `src` al video —
 * no basta con pausarlo: un mp4 pausado sigue bajando bytes en segundo plano.
 */
(function () {
  "use strict";

  var ventana = null;
  var video = null;
  var titulo = null;
  var quienAbrio = null;
  var apagados = [];

  /* `aria-modal="true"` promete que el resto de la página queda fuera de alcance, y hasta el review
   * v10 (FE-01) era solo una promesa: se abría el video, se pulsaba Tab un par de veces y el foco se
   * iba a los enlaces de detrás del overlay — invisibles, pero enfocables.
   *
   * `inert` y no un trampa-foco a mano: apagar el fondo es la misma garantía en una línea, y además
   * lo esconde del lector de pantalla, que un ciclo de Tab no hace. Se guarda a quién se apagó para
   * no encender al cerrar algo que ya estaba apagado por otro motivo.
   *
   * Donde el navegador no conozca `inert` esto no hace nada y el modal se comporta como antes: no
   * mejora, pero tampoco rompe.
   */
  function aislarFondo(encender) {
    if (encender) {
      Array.prototype.forEach.call(document.body.children, function (hijo) {
        if (hijo !== ventana && !hijo.inert) {
          hijo.inert = true;
          apagados.push(hijo);
        }
      });
      return;
    }
    apagados.forEach(function (hijo) { hijo.inert = false; });
    apagados = [];
  }

  function armar() {
    ventana = document.createElement("div");
    ventana.className = "dgl-modal";
    ventana.hidden = true;
    ventana.setAttribute("role", "dialog");
    ventana.setAttribute("aria-modal", "true");
    ventana.innerHTML =
      '<div class="dgl-modal-caja">' +
      '<div class="dgl-modal-barra"><span class="dgl-modal-titulo"></span>' +
      '<button type="button" class="dgl-modal-cerrar" aria-label="Cerrar">×</button></div>' +
      '<video class="dgl-modal-video" controls playsinline preload="none"></video>' +
      "</div>";
    document.body.appendChild(ventana);

    video = ventana.querySelector(".dgl-modal-video");
    titulo = ventana.querySelector(".dgl-modal-titulo");

    ventana.querySelector(".dgl-modal-cerrar").addEventListener("click", cerrar);
    // Solo el fondo cierra; un clic dentro de la caja no, que si no se cerraría al usar los controles.
    ventana.addEventListener("click", function (e) { if (e.target === ventana) { cerrar(); } });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !ventana.hidden) { cerrar(); } });
  }

  function abrir(boton) {
    if (!ventana) { armar(); }
    quienAbrio = boton;
    titulo.textContent = boton.dataset.titulo || "";
    ventana.setAttribute("aria-label", boton.dataset.titulo || "Video");
    video.poster = boton.dataset.portada || "";
    video.src = boton.dataset.video;
    ventana.hidden = false;
    aislarFondo(true);
    document.body.classList.add("dgl-sin-scroll");
    video.play().catch(function () { /* si el navegador no deja arrancar solo, quedan los controles */ });
    ventana.querySelector(".dgl-modal-cerrar").focus();
  }

  function cerrar() {
    if (!ventana || ventana.hidden) { return; }
    video.pause();
    video.removeAttribute("src");
    video.load();  // corta la descarga; sin esto el mp4 sigue bajando con la ventana cerrada
    ventana.hidden = true;
    // Encender el fondo ANTES de devolver el foco: un elemento inerte no se puede enfocar, así que
    // al revés el `focus()` de abajo no haría nada y quien navega con teclado acabaría en el body.
    aislarFondo(false);
    document.body.classList.remove("dgl-sin-scroll");
    // Devolver el foco a donde estaba: si no, quien navega con teclado vuelve al principio de todo.
    if (quienAbrio && document.contains(quienAbrio)) { quienAbrio.focus(); }
    quienAbrio = null;
  }

  document.addEventListener("click", function (e) {
    var boton = e.target.closest(".dgl-video");
    if (boton && boton.dataset.video) {
      e.preventDefault();
      abrir(boton);
    }
  });
})();
