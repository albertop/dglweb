// El widget de líderes: las pestañas de oficio y el «ver más».
//
// Todo el contenido viene ya en el HTML —son unas treinta filas— y acá solo se muestra u oculta. Eso
// significa que sin JavaScript la página sigue sirviendo: se ve la primera pestaña con sus métricas
// principales, que es información correcta, solo que menos.
//
// La marcación de pestañas accesible (role, aria-selected, flechas del teclado) se agrega desde acá y
// no en la plantilla a propósito: prometer `role="tablist"` sin el JS que cumple su contrato de
// teclado es peor que no prometer nada, porque un lector de pantalla anuncia un comportamiento que la
// página no tiene.
(function () {
  var caja = document.querySelector('.dgl-lideres');
  if (!caja) return;

  var pestanas = Array.prototype.slice.call(caja.querySelectorAll('.dgl-lideres-tab'));
  var listas = Array.prototype.slice.call(caja.querySelectorAll('.dgl-lideres-lista'));
  var mas = caja.querySelector('.dgl-lideres-mas');
  var abierto = false;

  // ── Pestañas ────────────────────────────────────────────────────────────────────────────────
  var tabs = caja.querySelector('.dgl-lideres-tabs');
  tabs.setAttribute('role', 'tablist');

  pestanas.forEach(function (pestana, i) {
    var lista = listas[i];
    var id = 'lideres-' + pestana.dataset.oficio;
    pestana.setAttribute('role', 'tab');
    pestana.id = id + '-tab';
    pestana.setAttribute('aria-controls', id);
    pestana.setAttribute('aria-selected', i === 0 ? 'true' : 'false');
    // Solo la pestaña activa es tabulable: el grupo entero se recorre con las flechas, que es como
    // se espera que funcione un tablist.
    pestana.tabIndex = i === 0 ? 0 : -1;
    lista.setAttribute('role', 'tabpanel');
    lista.id = id;
    lista.setAttribute('aria-labelledby', id + '-tab');
  });

  function mostrar(i, mover) {
    pestanas.forEach(function (pestana, j) {
      var activa = i === j;
      pestana.classList.toggle('is-on', activa);
      pestana.setAttribute('aria-selected', activa ? 'true' : 'false');
      pestana.tabIndex = activa ? 0 : -1;
      listas[j].classList.toggle('d-none', !activa);
    });
    if (mover) pestanas[i].focus();
  }

  pestanas.forEach(function (pestana, i) {
    pestana.addEventListener('click', function () { mostrar(i, false); });
    pestana.addEventListener('keydown', function (e) {
      var salto = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
      if (!salto) return;
      e.preventDefault();
      mostrar((i + salto + pestanas.length) % pestanas.length, true);
    });
  });

  // ── Ver más ─────────────────────────────────────────────────────────────────────────────────
  // Una sola vez para las dos pestañas: si se abriera por pestaña, cambiar de oficio cerraría lo que
  // el lector acababa de abrir.
  if (!mas) return;
  if (!caja.querySelector('.dgl-de-mas')) { mas.remove(); return; }  // no hay nada más que enseñar

  mas.addEventListener('click', function () {
    abierto = !abierto;
    Array.prototype.forEach.call(caja.querySelectorAll('.dgl-de-mas'), function (fila) {
      fila.classList.toggle('d-none', !abierto);
    });
    mas.textContent = abierto ? 'ver menos' : 'ver más';
    mas.setAttribute('aria-expanded', abierto ? 'true' : 'false');
  });
})();
