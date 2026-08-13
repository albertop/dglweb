/* El generador de comparaciones: enseña y esconde los campos según la modalidad, y llena el
 * desplegable de temporadas con los años del pelotero elegido.
 *
 * NO VALIDA NADA. El servidor vuelve a comprobarlo todo en `_validar`, y tiene que hacerlo: la URL
 * se puede escribir a mano. Lo que se gana acá es que el camino equivocado no esté disponible — un
 * desplegable que solo ofrece años comparables evita el error en vez de explicarlo después.
 *
 * SIN ESTE ARCHIVO el formulario no se puede usar, pero tampoco se podría sin `buscador.js`: elegir
 * un pelotero ya depende del navegador. La página no finge lo contrario.
 *
 * DOS CONTRATOS, los dos por atributo:
 *   data-visible-si="id-del-radio"   el bloque se ve solo con ese radio marcado.
 *   data-anios="URL" data-elegido="id-del-campo-oculto"   el <select> se llena con los años de ese.
 *   data-elegido-valor="YYYY"          el año que ya estaba puesto, para no perderlo al recargar.
 * Añadir una modalidad es un radio y un bloque, sin tocar este archivo.
 */
(function () {
  "use strict";

  var form = document.getElementById("cmp-form");
  if (!form) return;

  var dependientes = Array.prototype.slice.call(form.querySelectorAll("[data-visible-si]"));
  var selectores = Array.prototype.slice.call(form.querySelectorAll("[data-anios]"));

  // ── el desplegable de años ──────────────────────────────────────────────────────────────────
  function llenar(select, anios) {
    // EL AÑO QUE YA HABÍA ELEGIDO, que al volver del servidor NO está en `select.value`: el desplegable
    // llega vacío y se llena después. Por eso el servidor lo manda aparte, en `data-elegido-valor`.
    //
    // SIN ESTO, VOLVER DEL RESUMEN AL PASO 5 CAMBIABA LA COMPARACIÓN EN SILENCIO: el `<select>` se
    // llenaba y se quedaba con el primer año de la lista, no con el que el usuario había puesto. Pulsar
    // «Siguiente» sin mirar generaba otra tarjeta.
    var antes = select.dataset.elegidoValor || select.value;

    select.innerHTML = "";
    if (!anios.length) {
      select.disabled = true;
      return;
    }
    anios.forEach(function (anio) {
      var opcion = document.createElement("option");
      opcion.value = anio;
      opcion.textContent = anio;
      select.appendChild(opcion);
    });
    if (anios.indexOf(parseInt(antes, 10)) >= 0) select.value = antes;
    // Solo se habilita si su bloque está a la vista; si no, volvería a enviarse un año que la
    // modalidad elegida no pidió.
    select.disabled = !visible(select);
  }

  function visible(campo) {
    var bloque = campo.closest("[data-visible-si]");
    if (!bloque) return true;
    var radio = document.getElementById(bloque.dataset.visibleSi);
    return !!(radio && radio.checked);
  }

  function cargar(select) {
    var oculto = document.getElementById(select.dataset.elegido);
    var slug = oculto ? oculto.value : "";
    if (!slug) {
      llenar(select, []);
      return;
    }
    fetch(select.dataset.anios + "?jugador=" + encodeURIComponent(slug))
      .then(function (r) {
        return r.json();
      })
      .then(function (d) {
        // Se comprueba que el pelotero siga siendo el mismo: quien cambia de opinión rápido puede
        // tener dos respuestas en vuelo, y la vieja pintaría los años del anterior.
        if (oculto.value === slug) llenar(select, d.anios || []);
      })
      .catch(function () {
        llenar(select, []); // sin años; el servidor dirá que falta elegir la temporada
      });
  }

  // ── los bloques que dependen de la modalidad ────────────────────────────────────────────────
  function sincronizar() {
    dependientes.forEach(function (bloque) {
      var radio = document.getElementById(bloque.dataset.visibleSi);
      var toca = !!(radio && radio.checked);
      bloque.classList.toggle("d-none", !toca);
      bloque.querySelectorAll("input, select").forEach(function (campo) {
        // `disabled` y no solo escondido: un campo invisible que sigue enviándose deja al servidor
        // leyendo un año que el usuario no pidió, y eso es justo el tipo de decisión silenciosa que
        // no queremos. Los desplegables vacíos se quedan apagados aunque toque verlos: no hay nada
        // que elegir hasta que se elija al pelotero.
        campo.disabled = !toca || (campo.tagName === "SELECT" && !campo.options.length);
      });
    });
  }

  form.addEventListener("change", function (evento) {
    if (evento.target.name === "modo") {
      sincronizar();
      return;
    }
    // Elegir un pelotero cambia sus años. `buscador.js` dispara `change` sobre el campo oculto.
    selectores.forEach(function (select) {
      if (select.dataset.elegido !== evento.target.id) return;
      // CAMBIAR DE PELOTERO BORRA LA MEMORIA DEL AÑO, las DOS (review v25, DEV-01). El `dataset` es
      // estado restaurado del servidor y `value` es lo que el usuario eligió antes, pero los dos son
      // de OTRO pelotero: heredarlos deja el desplegable en un año que nadie pidió para él. El
      // cálculo saldría correcto para lo que se envía y aun así no sería lo que se pidió.
      select.dataset.elegidoValor = "";
      select.value = "";
      cargar(select);
    });
  });

  sincronizar();
  // Al volver del servidor con un pelotero ya puesto, sus años se cargan sin tocar nada.
  selectores.forEach(function (select) {
    var oculto = document.getElementById(select.dataset.elegido);
    if (oculto && oculto.value) cargar(select);
  });

  // El foco a los errores al volver del servidor. Vienen de una recarga completa, así que sin esto
  // quien navega con teclado o lector de pantalla se queda al principio de la página sin enterarse
  // de que su comparación no se hizo.
  var errores = document.getElementById("errores");
  if (errores) errores.focus();
})();
