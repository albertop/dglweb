// La señal de «cargando» del tablero de Líderes.
//
// Estaba como bloque `<script>` dentro de `leaders.html` y salió por la CSP, que no ejecuta scripts
// inline. Ver `core/csp.py`. Va en archivo aparte y no en `lideres.js` porque ese es el WIDGET de la
// portada —que esta página también carga—, y son dos cosas distintas con el nombre parecido.
//
// Por qué existe: acá cada selección es una URL propia —el tablero es indexable, esa fue la
// decisión— así que cambiar de métrica es un viaje al servidor. Sin señal, el navegador se queda
// quieto medio segundo y parece que el clic no hizo nada.

(function () {
  var caja = document.getElementById("dgl-loading");
  if (!caja) return;

  function encender() {
    caja.classList.add("is-on");
  }

  // Los selectores navegan por acá en vez de con un `onchange` inline: enciende la señal ANTES de
  // irse, que es todo el punto.
  document.addEventListener("change", function (evento) {
    var control = evento.target.closest("[data-ir]");
    if (!control || !control.value) return;
    encender();
    location.href = control.value;
  });

  // Los tabs y pills de esta página son `<a>` —cada tablero es su propia URL— y no `<button>` como
  // en el perfil, así que también disparan un viaje al servidor.
  document.querySelectorAll(".nav-tabs .nav-link, .nav-pills .nav-link").forEach(function (a) {
    a.addEventListener("click", encender);
  });

  // Al volver con el botón atrás, la página se restaura del bfcache TAL COMO QUEDÓ — con el overlay
  // puesto. `pageshow` corre también en esa restauración; `load` no.
  window.addEventListener("pageshow", function () {
    caja.classList.remove("is-on");
  });
})();
