/* Mejora los botones de compartir donde el navegador da más de lo que da un enlace.
 *
 * LO IMPORTANTE: SIN ESTE ARCHIVO TODO SIGUE FUNCIONANDO
 * ------------------------------------------------------
 * Los cuatro botones son `<a href>` planos a la URL de compartir de cada red. Funcionan sin
 * JavaScript, no cargan nada de terceros y no rastrean a nadie — que es lo que permite la CSP de este
 * sitio, y lo que sostiene la política de cookies.
 *
 * Acá solo se añaden dos cosas ENCIMA:
 *
 *   1. El menú NATIVO del sistema (`navigator.share`), en los navegadores que lo traen. Es lo único
 *      que alcanza a Instagram, que no tiene URL de compartir, y lo que le da a la persona la lista
 *      de apps que de verdad usa en vez de las tres que elegimos nosotros.
 *
 *   2. Que «Copiar enlace» copie de verdad. Sin JavaScript ese botón es un enlace al propio artículo:
 *      no copia, pero tampoco miente ni queda muerto.
 *
 * POR QUÉ EL BOTÓN NATIVO NACE OCULTO Y SE ENSEÑA ACÁ
 * ----------------------------------------------------
 * `navigator.share` no existe en la mayoría de los navegadores de escritorio. Dibujarlo siempre y
 * esconderlo cuando falla dejaría un botón muerto en la mitad de las visitas; así solo aparece donde
 * hace algo.
 */
(function () {
  "use strict";

  var COPIADO_MS = 1800;

  function copiar(texto) {
    /* `clipboard-write` solo existe en contextos seguros. En https lo hay; el respaldo es para el
     * desarrollo local por http, donde si no existiera el botón no haría nada y parecería roto. */
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(texto);
    }
    return new Promise(function (resolver, rechazar) {
      var caja = document.createElement("textarea");
      caja.value = texto;
      /* Fuera de la vista pero DENTRO del documento: un elemento con `display:none` no se puede
       * seleccionar, así que `execCommand` no copiaría nada. */
      caja.style.cssText = "position:fixed;top:-9999px;opacity:0";
      document.body.appendChild(caja);
      caja.select();
      try {
        document.execCommand("copy") ? resolver() : rechazar();
      } catch (e) {
        rechazar(e);
      }
      document.body.removeChild(caja);
    });
  }

  function avisar(boton, texto) {
    /* SE ESCRIBE EN EL `<span>`, NO EN EL BOTÓN. Asignar `textContent` al botón borra TODOS sus
     * hijos, y el icono en SVG es uno de ellos: el aviso se deshace a los dos segundos pero el icono
     * no vuelve, así que el botón se quedaba de texto pelado y desalineado respecto a los otros
     * cuatro para el resto de la visita. No revienta nada — solo se ve mirando, y estuvo así hasta
     * que lo cazó una prueba.
     *
     * El respaldo al botón es para no depender de la forma exacta del marcado. */
    var destino = boton.querySelector("span") || boton;
    if (boton.dataset.textoOriginal === undefined) {
      boton.dataset.textoOriginal = destino.textContent;
    }
    destino.textContent = texto;
    clearTimeout(boton._temporizador);
    boton._temporizador = setTimeout(function () {
      destino.textContent = boton.dataset.textoOriginal;
    }, COPIADO_MS);
  }

  function montar(caja) {
    var url = caja.dataset.url;
    var titulo = caja.dataset.titulo;

    var nativo = caja.querySelector("[data-compartir-nativo]");
    if (nativo && navigator.share) {
      nativo.hidden = false;
      nativo.classList.remove("d-none");
      nativo.addEventListener("click", function () {
        /* El `catch` NO es opcional: cerrar el menú del sistema sin elegir nada rechaza la promesa
         * con `AbortError`, y sin atraparlo eso sale como error en la consola de cada visita. */
        navigator.share({ title: titulo, text: titulo, url: url }).catch(function () {});
      });
    }

    var copiarBoton = caja.querySelector("[data-copiar]");
    if (copiarBoton) {
      copiarBoton.addEventListener("click", function (evento) {
        evento.preventDefault(); // sin esto, navegaría al propio artículo
        copiar(url).then(
          function () {
            avisar(copiarBoton, "¡Copiado!");
          },
          function () {
            /* Si el navegador no deja copiar, se dice. Un botón que no hace nada y no avisa es peor
             * que uno que reconoce que no pudo. */
            avisar(copiarBoton, "No se pudo copiar");
          }
        );
      });
    }
  }

  function montarTodos() {
    var cajas = document.querySelectorAll("[data-compartir]");
    for (var i = 0; i < cajas.length; i++) montar(cajas[i]);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", montarTodos);
  } else {
    montarTodos();
  }
})();
