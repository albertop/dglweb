// Los dos comportamientos que valen para TODAS las páginas. Estaban escritos dentro del HTML —uno
// como bloque `<script>` en `base.html` y el otro como atributo `onerror` en dos plantillas— y de
// ahí salieron por la CSP: con `script-src 'self'`, el navegador no ejecuta ni scripts inline ni
// manejadores en atributos. Ver `core/csp.py`.
//
// No es solo un requisito de la cabecera: un `onclick="..."` en el HTML es JavaScript que no aparece
// en ningún archivo `.js`, así que no se busca, no se prueba y se duplica sin que nadie lo note. Los
// cuatro «desglose» del perfil eran literalmente la misma línea escrita cuatro veces.

(function () {
  // El enlace «desglose» de una fila de totales salta a su pill. Clicquea el botón de nav en vez de
  // mostrar el panel a mano, así Bootstrap hace todo y no queda un estado a medias.
  //
  // Va DELEGADO en el documento y no enganchado a cada botón: las tablas del perfil se dibujan
  // enteras desde el servidor, pero un listener por botón son cuatro listeners para el mismo
  // comportamiento, y si algún día una tabla llega por AJAX este sigue funcionando sin tocar nada.
  document.addEventListener("click", function (evento) {
    var boton = evento.target.closest("[data-pill]");
    if (!boton) return;
    var nav = document.querySelector(
      '[data-bs-toggle="pill"][data-bs-target="#' + boton.dataset.pill + '"]'
    );
    if (nav) {
      nav.click();
      nav.scrollIntoView({ block: "nearest" });
    }
  });

  // Las fotos que faltan se quitan en vez de dejar el icono de imagen partida: un debutante al que
  // MLB todavía no ha retratado no tiene por qué ensuciar el widget.
  //
  // `true` al final NO es opcional. El evento `error` de una imagen no burbujea, así que un listener
  // normal en el documento no se entera nunca; solo lo ve la fase de captura. Es la razón por la que
  // esto vivía como atributo `onerror` y no como listener.
  document.addEventListener(
    "error",
    function (evento) {
      var img = evento.target;
      if (img.tagName === "IMG" && img.dataset.quitarSiFalta !== undefined) img.remove();
    },
    true
  );
})();

// El «ver más» de un widget que esconde parte de su lista. Hoy lo usa el de destacados.
//
// Delegado y genérico: el botón dice a qué contenedor pertenece con `data-desplegar`, así que sumar
// otro widget con la misma mecánica no pide JavaScript nuevo. Y va acá y no en un archivo propio
// porque son diez líneas — un archivo más sería una petición más por visita para esto.
//
// NO mide nada, a diferencia del widget de líderes: aquel tiene una rejilla que cambia de columnas
// con el ancho y hay que preguntarle al navegador cuántas cajas caben. La de destacados es fija —2
// por 3— así que el corte lo decide el servidor y acá solo se abre y se cierra.
(function () {
  document.addEventListener("click", function (evento) {
    var boton = evento.target.closest("[data-desplegar]");
    if (!boton) return;
    var caja = document.querySelector(boton.dataset.desplegar);
    if (!caja) return;
    var abierto = caja.classList.toggle("esta-desplegado");
    boton.setAttribute("aria-expanded", abierto ? "true" : "false");
    // El texto tiene que cambiar: un botón que sigue diciendo «Ver 4 más» con las cuatro ya a la
    // vista miente, y deja al lector sin saber cómo volver a cerrarlo.
    if (abierto) {
      boton.dataset.textoCerrado = boton.textContent;
      boton.textContent = "Ver menos";
    } else if (boton.dataset.textoCerrado) {
      boton.textContent = boton.dataset.textoCerrado;
    }
  });
})();
