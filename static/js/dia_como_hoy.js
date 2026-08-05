/* La rotación de «Un día como hoy».
 *
 * QUÉ HACE Y QUÉ NO
 * -----------------
 * Las dieciséis tarjetas ya están TODAS en la página, pintadas por el servidor. Esto solo decide
 * cuáles se ven. No pide nada, no consulta nada y si no llega a cargar el widget se queda enseñando
 * las primeras, que son las de más puntaje del día.
 *
 * LA VENTANA MIDE DOS O UNA, Y LO DECIDE EL ANCHO
 * ----------------------------------------------
 * En el `.container` caben dos tarjetas y en un teléfono cabe una, así que en escritorio hay ocho
 * pantallas y en móvil dieciséis. El servidor no puede saber cuál de las dos, y por eso manda las
 * tarjetas sueltas en vez de emparejadas: quien las agrupa es esto, mirando la MISMA consulta de
 * ancho que usa el CSS para poner una o dos columnas. Si las dos se separan, el móvil enseña dos
 * tarjetas encima de la otra.
 *
 * POR QUÉ CADA PANTALLA DURA LO SUYO Y NO UN TIEMPO FIJO
 * -----------------------------------------------------
 * Porque «Cumple 70 años.» son quince caracteres y la entrada más larga del archivo son doscientos
 * cincuenta. Con un intervalo fijo, o el corto se eterniza o el largo se va antes de que termines.
 * Cada tarjeta trae en `data-ms` lo que cuesta leerla —la cuenta está en `_ms()` de
 * `stats/efemerides.py`, que es donde se puede probar— y acá se suman las que se ven y se aplican el
 * suelo y el techo, que vienen en `data-min` y `data-max`.
 *
 * Es la misma idea que `cintillo.js`: lo que tiene que quedar constante no es la duración, es el
 * ritmo al que se lee.
 */
(function () {
  "use strict";

  var caja = document.getElementById("dia-como-hoy");
  if (!caja) return;

  var tarjetas = Array.prototype.slice.call(caja.querySelectorAll(".dgl-dch-caja"));
  if (!tarjetas.length) return;

  var controles = document.querySelector(".dgl-dch-controles");
  var contenedorPuntos = controles && controles.querySelector(".dgl-dch-puntos");
  var cuenta = controles && controles.querySelector(".dgl-dch-cuenta");

  var minimo = parseInt(caja.getAttribute("data-min"), 10) || 10000;
  var maximo = parseInt(caja.getAttribute("data-max"), 10) || 24000;

  // QUIEN PIDIÓ QUE NADA SE MUEVA, MANDA. El CSS ya enseña las dieciséis apiladas con
  // `prefers-reduced-motion`, así que acá solo hay que no arrancar y no destapar los controles: no
  // hay nada que adelantar cuando está todo a la vista. Es la misma cortesía que congela el cintillo.
  var quieto = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)");
  if (quieto && quieto.matches) return;

  // El mismo corte que el CSS usa para pasar de una columna a dos. Si los dos se separan, el móvil
  // enseñaría dos tarjetas en la misma celda de la retícula, una encima de la otra.
  var ancha = window.matchMedia("(min-width: 768px)");

  var porPantalla = 1;
  var pantallas = 1;
  var actual = 0;
  var reloj = null;
  var detenido = false;

  function delaPantalla(indice) {
    return tarjetas.slice(indice * porPantalla, indice * porPantalla + porPantalla);
  }

  function pintar(indice) {
    // Se normaliza acá y no en cada llamador: «Anterior» desde la primera tiene que ir a la última,
    // y el `%` de JavaScript con negativos devuelve negativo.
    actual = ((indice % pantallas) + pantallas) % pantallas;
    var visibles = delaPantalla(actual);
    tarjetas.forEach(function (t) {
      t.classList.toggle("es-visible", visibles.indexOf(t) !== -1);
    });
    if (contenedorPuntos) {
      Array.prototype.forEach.call(contenedorPuntos.children, function (punto, i) {
        punto.classList.toggle("es-visible", i === actual);
        // `aria-current` y no `aria-selected`: esto no es una pestaña, es una posición dentro de una
        // lista. Sin él, los puntos suenan todos iguales y no hay forma de saber dónde se está.
        if (i === actual) punto.setAttribute("aria-current", "true");
        else punto.removeAttribute("aria-current");
      });
    }
    if (cuenta) cuenta.textContent = actual + 1 + " / " + pantallas;
  }

  function cuantoDura() {
    var suma = delaPantalla(actual).reduce(function (total, t) {
      return total + (parseInt(t.getAttribute("data-ms"), 10) || 0);
    }, 0);
    return Math.min(maximo, Math.max(minimo, suma));
  }

  function programar() {
    // Siempre se limpia antes de armar. Sin esto, pulsar «Próximo» mientras corre el reloj deja dos
    // temporizadores vivos y el widget empieza a saltarse pantallas de dos en dos.
    if (reloj) clearTimeout(reloj);
    if (detenido || pantallas < 2) return;
    reloj = setTimeout(function () {
      pintar(actual + 1);
      programar();
    }, cuantoDura());
  }

  function parar() {
    detenido = true;
    if (reloj) clearTimeout(reloj);
  }

  function seguir() {
    detenido = false;
    programar();
  }

  function ir(indice) {
    pintar(indice);
    // Se rearma desde cero: quien acaba de pedir una pantalla concreta merece los segundos enteros
    // de esa pantalla, no lo que quedaba de la anterior.
    programar();
  }

  /* Rehace el reparto: cuántas caben, cuántas pantallas salen y los puntos que hacen falta.
   *
   * Se llama al arrancar y cada vez que se cruza el corte de 768px — girar un teléfono pasa de una
   * a dos y de dieciséis pantallas a ocho, y los puntos de antes ya no valen. */
  function repartir() {
    var antes = porPantalla;
    porPantalla = ancha.matches ? 2 : 1;
    pantallas = Math.ceil(tarjetas.length / porPantalla);

    // SE CONSERVA LA TARJETA QUE SE ESTABA MIRANDO, no el número de pantalla. Al girar el teléfono,
    // la pantalla 6 de dieciséis no es la 6 de ocho — quien iba por la duodécima efeméride tiene que
    // seguir viéndola, no saltar a la séptima.
    var tarjetaActual = actual * antes;
    actual = Math.floor(tarjetaActual / porPantalla);

    if (contenedorPuntos) {
      contenedorPuntos.textContent = "";
      for (var i = 0; i < pantallas; i++) {
        var punto = document.createElement("button");
        punto.type = "button";
        punto.className = "dgl-dch-punto";
        punto.setAttribute("aria-label", "Efemérides " + (i + 1) + " de " + pantallas);
        punto.addEventListener("click", ir.bind(null, i));
        contenedorPuntos.appendChild(punto);
      }
    }

    // Los controles solo aparecen si hay a dónde ir. Con dos efemérides en escritorio hay una sola
    // pantalla, y unas flechas que no mueven nada son un botón roto.
    if (controles) controles.hidden = pantallas < 2;

    pintar(actual);
    programar();
  }

  // El estado de «sin JavaScript» ya cumplió: a partir de acá manda `es-visible`.
  tarjetas.forEach(function (t) {
    t.classList.remove("es-primera", "es-segunda");
  });

  // SE PARA CUANDO ALGUIEN ESTÁ MIRÁNDOLO. Con el ratón encima o con el foco dentro, la persona está
  // leyendo o va camino de un enlace; cambiarle la tarjeta debajo es quitarle lo que estaba leyendo.
  // La pizarra hace lo mismo con su refresco.
  caja.addEventListener("mouseenter", parar);
  caja.addEventListener("mouseleave", seguir);
  caja.addEventListener("focusin", parar);
  caja.addEventListener("focusout", seguir);

  // Y CUANDO LA PESTAÑA NO SE VE. No es por ahorrar: es que al volver, el navegador dispara el
  // temporizador atrasado de golpe y el widget salta de pantalla sin que nadie lo haya visto pasar.
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) parar();
    else seguir();
  });

  if (controles) {
    controles.addEventListener("click", function (evento) {
      var boton = evento.target.closest("[data-dch-mover]");
      if (!boton) return;
      ir(actual + parseInt(boton.getAttribute("data-dch-mover"), 10));
    });
  }

  // `addEventListener` sobre el `MediaQueryList` y no `addListener`, que está obsoleto. Safari lo
  // soporta desde la 14; en uno más viejo el widget se queda con el reparto de la carga, que es
  // exactamente lo que hacía antes de existir esta línea.
  if (ancha.addEventListener) ancha.addEventListener("change", repartir);

  repartir();
})();
