// Pestañas de widget, compartidas por los destacados y por los líderes.
//
// Vive aparte porque las dos las necesitan idénticas —incluida la plomería de accesibilidad— y
// duplicarla llevaba a que una se arreglara y la otra no.
//
// El marcado que espera, dentro de un elemento con `data-pestanas`:
//
//   <div class="dgl-pestanas">
//     <button class="dgl-pill" data-oficio="bateo">Bateo</button>
//     <button class="dgl-pill" data-oficio="pitcheo">Pitcheo</button>
//   </div>
//   <div class="dgl-oficio" data-oficio="bateo">…</div>
//   <div class="dgl-oficio d-none" data-oficio="pitcheo">…</div>
//
// Los `role`, los `aria-*` y las flechas del teclado los pone este script y NO la plantilla:
// prometer `role="tablist"` sin el JS que cumple su contrato de teclado es peor que no prometer
// nada, porque un lector de pantalla anuncia un comportamiento que la página no tiene. Sin este
// archivo quedan dos botones inertes y la primera lista visible, que es información correcta.
//
// Al cambiar de pestaña dispara `dgl:pestana` sobre el contenedor, para que el widget que lo
// necesite —líderes cierra sus capas flotantes— reaccione sin que este archivo sepa de eso.
(function () {
  Array.prototype.forEach.call(document.querySelectorAll('[data-pestanas]'), function (caja) {
    var tabs = caja.querySelector('.dgl-pestanas');
    if (!tabs) return;

    var pestanas = Array.prototype.slice.call(tabs.querySelectorAll('[data-oficio]'));
    var paneles = Array.prototype.slice.call(caja.querySelectorAll('.dgl-oficio'));
    if (pestanas.length !== paneles.length) return;

    var semilla = 'oficio-' + (caja.id || Math.abs(pestanas.length * 7 + paneles.length));
    tabs.setAttribute('role', 'tablist');

    pestanas.forEach(function (pestana, i) {
      var id = semilla + '-' + pestana.dataset.oficio;
      pestana.setAttribute('role', 'tab');
      pestana.id = id + '-tab';
      pestana.setAttribute('aria-controls', id);
      pestana.setAttribute('aria-selected', i === 0 ? 'true' : 'false');
      // Solo la activa es tabulable: el grupo se recorre con las flechas, que es como se espera que
      // funcione un tablist.
      pestana.tabIndex = i === 0 ? 0 : -1;
      paneles[i].setAttribute('role', 'tabpanel');
      paneles[i].id = id;
      paneles[i].setAttribute('aria-labelledby', id + '-tab');
    });

    function mostrar(i, mover) {
      pestanas.forEach(function (pestana, j) {
        var esta = i === j;
        pestana.classList.toggle('active', esta);
        pestana.setAttribute('aria-selected', esta ? 'true' : 'false');
        pestana.tabIndex = esta ? 0 : -1;
        paneles[j].classList.toggle('d-none', !esta);
      });
      if (mover) pestanas[i].focus();
      caja.dispatchEvent(new CustomEvent('dgl:pestana', { detail: { indice: i } }));
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
  });
})();
