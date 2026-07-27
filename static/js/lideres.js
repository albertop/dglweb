// El widget de líderes: las pestañas de oficio y el «ver más» de cada caja.
//
// Todo el contenido viene ya en el HTML —son unas treinta filas— y acá solo se muestra u oculta. Sin
// JavaScript la página sigue sirviendo: se ve la primera pestaña con el líder de cada categoría, que
// es información correcta, solo que menos.
//
// La marcación de pestañas accesible (role, aria-selected, flechas del teclado) se agrega desde acá y
// no en la plantilla a propósito: prometer `role="tablist"` sin el JS que cumple su contrato de
// teclado es peor que no prometer nada, porque un lector de pantalla anuncia un comportamiento que la
// página no tiene.
(function () {
  var caja = document.querySelector('.dgl-lideres');
  if (!caja) return;

  // ── Pestañas ────────────────────────────────────────────────────────────────────────────────
  var pestanas = Array.prototype.slice.call(caja.querySelectorAll('.dgl-lideres-tab'));
  var listas = Array.prototype.slice.call(caja.querySelectorAll('.dgl-lideres-lista'));
  var tabs = caja.querySelector('.dgl-lideres-tabs');
  tabs.setAttribute('role', 'tablist');

  pestanas.forEach(function (pestana, i) {
    var id = 'lideres-' + pestana.dataset.oficio;
    pestana.setAttribute('role', 'tab');
    pestana.id = id + '-tab';
    pestana.setAttribute('aria-controls', id);
    pestana.setAttribute('aria-selected', i === 0 ? 'true' : 'false');
    // Solo la pestaña activa es tabulable: el grupo entero se recorre con las flechas, que es como
    // se espera que funcione un tablist.
    pestana.tabIndex = i === 0 ? 0 : -1;
    listas[i].setAttribute('role', 'tabpanel');
    listas[i].id = id;
    listas[i].setAttribute('aria-labelledby', id + '-tab');
  });

  function mostrar(i, mover) {
    pestanas.forEach(function (pestana, j) {
      var activa = i === j;
      pestana.classList.toggle('active', activa);
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

  // ── El «ver más» de cada caja ───────────────────────────────────────────────────────────────
  // Cada caja se abre y se cierra sola: abrir Bases robadas no tiene por qué mover Jonrones, que
  // está tres cajas más abajo y saltaría bajo el cursor del lector.
  //
  // Un solo escucha en el contenedor en vez de uno por botón: son hasta diecinueve cajas por
  // pestaña, y el que decide es el botón donde se hizo clic.
  caja.addEventListener('click', function (e) {
    var boton = e.target.closest('.dgl-lider-mas');
    if (!boton) return;

    var suCaja = boton.closest('.dgl-lider-caja');
    var abierto = boton.getAttribute('aria-expanded') === 'true';
    var ocultos = suCaja.querySelectorAll('.dgl-de-mas');

    Array.prototype.forEach.call(ocultos, function (fila) {
      fila.classList.toggle('d-none', abierto);
    });
    boton.setAttribute('aria-expanded', abierto ? 'false' : 'true');
    boton.textContent = abierto ? 'ver ' + ocultos.length + ' más' : 'ver menos';
    suCaja.classList.toggle('is-abierta', !abierto);
  });
})();
