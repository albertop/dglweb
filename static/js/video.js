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
