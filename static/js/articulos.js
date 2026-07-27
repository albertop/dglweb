/* «Ver más artículos»: destapa de doce en doce los que ya vienen en la página.
 *
 * Sin ir al servidor. Los artículos están dibujados y escondidos desde el HTML, así que el clic no
 * espera a nadie y sigue funcionando si la red se cae a mitad de lectura. El precio —que la página
 * traiga hasta 45 aunque se lean nueve— está asumido y explicado en la plantilla del índice.
 *
 * El botón nace VISIBLE y este script lo esconde si no hay nada que destapar. Al revés —nacer
 * escondido y que el JS lo muestre— dejaría el botón invisible justo cuando el script no carga, que
 * es cuando más falta hace saber que hay más artículos debajo.
 */
(function () {
  "use strict";

  var boton = document.getElementById("dgl-ver-mas");
  var zona = document.getElementById("dgl-mas-articulos");
  if (!boton || !zona) return;

  var porTanda = parseInt(zona.dataset.porTanda, 10) || 12;

  function ocultos() {
    return zona.querySelectorAll(".dgl-oculto[hidden]");
  }

  function ajustarBoton() {
    var quedan = ocultos().length;
    boton.hidden = quedan === 0;
    if (quedan === 0) return; // ya no se ve; reescribirlo solo dejaría un «Ver los 0 que quedan»
    // Decir CUÁNTOS quedan y no solo «ver más»: con 3 restantes, un botón que promete doce miente.
    boton.textContent = quedan > porTanda ? "Ver más artículos" : "Ver los " + quedan + " que quedan";
  }

  boton.addEventListener("click", function () {
    var tanda = Array.prototype.slice.call(ocultos(), 0, porTanda);
    tanda.forEach(function (columna) {
      columna.hidden = false;
    });
    ajustarBoton();
    // El foco se va a la primera tarjeta nueva. Sin esto, quien navega con teclado se queda con el
    // foco en un botón que puede haber desaparecido, y no tiene forma de saber que algo apareció.
    if (tanda.length) {
      var enlace = tanda[0].querySelector("a");
      if (enlace) {
        enlace.setAttribute("tabindex", "-1");
        enlace.focus({ preventScroll: true });
      }
    }
  });

  ajustarBoton();
})();
