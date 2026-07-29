/* Le pone el `src` al hueco horizontal de publicidad, eligiendo el tamaño que cabe en la pantalla.
 *
 * POR QUÉ ESTO EXISTE, Y NO ES UNA OPTIMIZACIÓN
 * ----------------------------------------------
 * Un hueco horizontal se vende en tres formatos —970×90, 728×90 y 320×50— y cada uno es una zona
 * distinta en Revive, porque Revive cuenta impresiones POR ZONA.
 *
 * La primera versión de esto dibujaba los tres `iframe` y ocultaba dos con `display: none`, dando por
 * hecho que un marco oculto no carga. **Es falso, y se comprobó en el navegador: los tres pidieron su
 * anuncio**, con `loading="lazy"` puesto y todo. Habrían sido tres impresiones por cada anuncio
 * realmente visto — el informe del anunciante inflado al triple, con dos tercios de anuncios que
 * nadie vio. En venta directa eso no es un defecto técnico, es facturar aire.
 *
 * Así que el marco nace SIN `src` —un `iframe` sin `src` no pide nada— y acá se le pone uno solo.
 *
 * POR QUÉ NO SE DECIDE EN EL SERVIDOR
 * ------------------------------------
 * Se podría mirar el `User-Agent` y mandar el tamaño ya elegido. Pero entonces el HTML dependería del
 * dispositivo y dejaría de poder cachearse en un CDN, y la Fase 8 del plan contempla Cloudflare.
 *
 * SIN JAVASCRIPT EL HUECO SE QUEDA VACÍO. Se acepta a conciencia: la alternativa era contar
 * impresiones falsas para todos los demás.
 */
(function () {
  "use strict";

  /* El ancho que se mide es el del CONTENEDOR, no el de la ventana. Es lo que decide de verdad si el
   * banner cabe: entre 992 y 1199 px de pantalla el `.container` de Bootstrap mide 960, así que un
   * banner de 970 se saldría aunque la ventana diera de sobra. Medido en el sitio real. */
  function anchoDisponible(marco) {
    var padre = marco.parentElement;
    return padre ? padre.clientWidth : window.innerWidth;
  }

  function elegir(opciones, disponible) {
    /* Las opciones vienen de mayor a menor. Se coge la primera que quepa: la que declara una pantalla
     * mínima menor o igual a la ventana Y cuyo ancho entre en el contenedor. Las dos condiciones,
     * porque el corte de pantalla es la regla de negocio y el ancho real es la comprobación. */
    for (var i = 0; i < opciones.length; i++) {
      var o = opciones[i];
      if (window.innerWidth >= o.min && o.ancho <= disponible) return o;
    }
    /* Si ni el más pequeño cabe —una pantalla de menos de 320 px— se devuelve ese igualmente: el
     * `max-width: 100%` del CSS lo encoge, y es mejor un banner apretado que un hueco vacío. */
    return opciones[opciones.length - 1];
  }

  function montar(marco) {
    if (marco.dataset.montado) return; // una vez y solo una: el segundo `src` sería otra impresión
    var opciones;
    try {
      opciones = JSON.parse(marco.dataset.anuncio);
    } catch (e) {
      return; // un atributo roto no puede tumbar la página
    }
    if (!opciones || !opciones.length) return;

    var elegida = elegir(opciones, anchoDisponible(marco));
    if (!elegida.url) return; // sin servidor de anuncios configurado

    marco.width = elegida.ancho;
    marco.height = elegida.alto;
    marco.dataset.montado = "1";
    marco.src = elegida.url;
  }

  function montarTodos() {
    var marcos = document.querySelectorAll("iframe.dgl-ad-marco[data-anuncio]");
    for (var i = 0; i < marcos.length; i++) montar(marcos[i]);
  }

  /* NO se vuelve a montar al cambiar el tamaño de la ventana, y es a propósito: cada `src` nuevo es
   * una impresión más que Revive le cobra al anunciante. Quien gire el teléfono o arrastre la ventana
   * se queda con el tamaño que le tocó al cargar — que se ve algo apretado o algo suelto, y ya. Es
   * preferible a cobrarle a Adcio por cada vez que alguien redimensiona. */
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", montarTodos);
  } else {
    montarTodos();
  }
})();
