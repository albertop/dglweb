/* La velocidad del cintillo, calculada a partir de lo que mide.
 *
 * POR QUÉ NO BASTA CON UNA DURACIÓN FIJA EN EL CSS
 * ------------------------------------------------
 * Porque la tira mide lo que midan los movimientos que haya. Con 25 entradas son unos 12.000px, y
 * los mismos 90 segundos daban 134px/s — se lee persiguiendo el texto. Pero en invierno, con tres
 * movimientos en una semana, esos mismos 90 segundos serían 27px/s y la cintilla parecería colgada.
 *
 * Lo que tiene que quedar constante es la VELOCIDAD, no la duración. Así que se mide la tira y se
 * calcula: duración = ancho / velocidad. Con eso el cintillo se lee igual en julio que en enero.
 *
 * Si este script no carga, manda la duración por defecto del CSS. Se ve, se mueve, y punto.
 */
(function () {
  "use strict";

  // Píxeles por segundo. 55 es paso de lectura: a 134 —lo que daba la duración fija— hay que
  // perseguir la frase con la vista, y el dueño lo notó de inmediato.
  var VELOCIDAD = 55;

  function ajustar() {
    var tira = document.querySelector(".dgl-cintillo-tira");
    if (!tira) return;
    // La lista va DOS veces dentro de la tira para que el ciclo empalme; la animación recorre la
    // mitad, así que lo que hay que medir es una sola.
    var una = tira.querySelector(".dgl-cintillo-lista");
    if (!una) return;
    var ancho = una.getBoundingClientRect().width;
    if (ancho > 0) tira.style.animationDuration = Math.round(ancho / VELOCIDAD) + "s";
  }

  ajustar();
  // Al cambiar el ancho de la ventana la tira no cambia de largo —las entradas no se parten, van en
  // una línea— pero sí puede cambiar con las fuentes ya cargadas. Recalcular es barato.
  window.addEventListener("load", ajustar);
})();
