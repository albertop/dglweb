/* Hace que el botón «Compartir…» de la tarjeta mande el PNG, y no solo el enlace.
 *
 * QUÉ CAMBIA. `compartir.js` monta ese botón en todo el sitio y comparte `{title, url}` — texto. Acá
 * se le engancha además el FICHERO, que es lo que de verdad llega como imagen a WhatsApp o a
 * Instagram. Los otros botones de la fila —WhatsApp, X, Facebook— no se tocan porque no se pueden:
 * sus URLs (`wa.me/?text=…` y compañía) solo aceptan texto. Lo que hace que ahí se vea la tarjeta es
 * el `og:image` de la página, no el botón.
 *
 * POR QUÉ SE INTERCEPTA EN CAPTURA. El botón ya trae su propio `click` de `compartir.js`. Escuchando
 * en fase de captura y parando la propagación, este se ejecuta primero y el otro no llega a correr —
 * si no, se compartirían las dos cosas o ganaría el que se registró antes, que depende del orden de
 * carga de los scripts y es justo lo que no se quiere que decida el comportamiento.
 *
 * SI ALGO FALLA NO SE ROMPE NADA: no se intercepta, y `compartir.js` hace lo de siempre con el
 * enlace. Peor comparación, no página rota.
 */
(function () {
  "use strict";

  var caja = document.querySelector("[data-png]");
  if (!caja || !navigator.canShare || !navigator.share) return;

  var boton = document.querySelector("[data-compartir-nativo]");
  if (!boton) return;

  var fichero = null;

  // La imagen ya está en la caché del navegador —es la que la página está mostrando— así que esto no
  // cuesta una descarga de más. Se prepara al cargar y no al pulsar: dentro del `click` habría que
  // esperar al `fetch`, y para entonces el navegador ya no considera el gesto «del usuario» y algunos
  // se niegan a abrir la hoja de compartir.
  fetch(caja.dataset.png)
    .then(function (r) {
      if (!r.ok) throw new Error("no se pudo leer la tarjeta");
      return r.blob();
    })
    .then(function (blob) {
      var candidato = new File([blob], caja.dataset.nombre || "comparacion.png", { type: "image/png" });
      // `canShare({files})` es la única prueba fiable de si este navegador manda ficheros, y necesita
      // un `File` de verdad. Si dice que no, se deja el botón como estaba: compartirá el enlace.
      if (navigator.canShare({ files: [candidato] })) fichero = candidato;
    })
    .catch(function () {
      /* se queda compartiendo el enlace */
    });

  boton.addEventListener(
    "click",
    function (evento) {
      if (!fichero) return; // que siga `compartir.js`
      evento.preventDefault();
      evento.stopImmediatePropagation();
      navigator
        .share({
          files: [fichero],
          title: document.title,
          // El enlace viaja con la imagen: quien la recibe puede volver acá y rehacer la comparación
          // con otros parámetros, que es lo que trae gente al sitio.
          text: window.location.href,
        })
        .catch(function () {
          // Cancelar la hoja llega acá como un rechazo. No es un error: el usuario dijo que no.
        });
    },
    true
  );
})();
