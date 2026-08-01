// Los dos comportamientos que valen para TODAS las páginas. Estaban escritos dentro del HTML —uno
// como bloque `<script>` en `base.html` y el otro como atributo `onerror` en dos plantillas— y de
// ahí salieron por la CSP: con `script-src 'self'`, el navegador no ejecuta ni scripts inline ni
// manejadores en atributos. Ver `core/csp.py`.
//
// No es solo un requisito de la cabecera: un `onclick="..."` en el HTML es JavaScript que no aparece
// en ningún archivo `.js`, así que no se busca, no se prueba y se duplica sin que nadie lo note. Los
// cuatro «desglose» del perfil eran literalmente la misma línea escrita cuatro veces.

(function () {
  // El enlace «desglose» de una fila de totales salta a su pill. Clicquea el botón de nav en vez de
  // mostrar el panel a mano, así Bootstrap hace todo y no queda un estado a medias.
  //
  // Va DELEGADO en el documento y no enganchado a cada botón: las tablas del perfil se dibujan
  // enteras desde el servidor, pero un listener por botón son cuatro listeners para el mismo
  // comportamiento, y si algún día una tabla llega por AJAX este sigue funcionando sin tocar nada.
  document.addEventListener("click", function (evento) {
    var boton = evento.target.closest("[data-pill]");
    if (!boton) return;
    var nav = document.querySelector(
      '[data-bs-toggle="pill"][data-bs-target="#' + boton.dataset.pill + '"]'
    );
    if (nav) {
      nav.click();
      nav.scrollIntoView({ block: "nearest" });
    }
  });

  // Las fotos que faltan se quitan en vez de dejar el icono de imagen partida: un debutante al que
  // MLB todavía no ha retratado no tiene por qué ensuciar el widget.
  //
  // `true` al final NO es opcional. El evento `error` de una imagen no burbujea, así que un listener
  // normal en el documento no se entera nunca; solo lo ve la fase de captura. Es la razón por la que
  // esto vivía como atributo `onerror` y no como listener.
  document.addEventListener(
    "error",
    function (evento) {
      var img = evento.target;
      if (img.tagName === "IMG" && img.dataset.quitarSiFalta !== undefined) img.remove();
    },
    true
  );
})();

// El «ver más» de un widget que esconde parte de su lista. SOLO ACTÚA EN MÓVIL, y no porque el
// JavaScript lo sepa: el CSS es el que recorta el marco por debajo de 992px y el que enseña el botón.
// Acá solo se pone y se quita la clase; en escritorio el botón está oculto y esto nunca se dispara.
//
// Existe otra vez desde el 2026-07-31. Se había borrado al quitar los botones, y volvió cuando se vio
// que en un teléfono la rejilla arma UNA columna: las diez cajas que en escritorio son cinco filas
// allí son diez, y el widget se convertía en un scroll interminable.
//
// Delegado y genérico: el botón dice a qué contenedor pertenece con `data-desplegar`, así que sumar
// otro widget con la misma mecánica no pide JavaScript nuevo.
//
// NO mide nada, a diferencia del widget de líderes: aquel tiene una rejilla que cambia de columnas
// con el ancho y hay que preguntarle al navegador cuántas cajas caben.
(function () {
  document.addEventListener("click", function (evento) {
    var boton = evento.target.closest("[data-desplegar]");
    if (!boton) return;
    var caja = document.querySelector(boton.dataset.desplegar);
    if (!caja) return;
    var abierto = caja.classList.toggle("esta-desplegado");
    boton.setAttribute("aria-expanded", abierto ? "true" : "false");
    // El texto tiene que cambiar: un botón que sigue diciendo «Ver 4 más» con las cuatro ya a la
    // vista miente, y deja al lector sin saber cómo volver a cerrarlo.
    if (abierto) {
      boton.dataset.textoCerrado = boton.textContent;
      boton.textContent = "Ver menos";
    } else if (boton.dataset.textoCerrado) {
      boton.textContent = boton.dataset.textoCerrado;
    }
  });
})();

// EL TOOLTIP DE LA LÍNEA QUE NO CABE. Sirve a los tres paneles de la franja —destacados y las dos
// rachas— porque los tres usan `.dgl-destacado-linea`.
//
// Va en JavaScript y no en la plantilla a propósito. La línea se manda ENTERA y el CSS la corta con
// `text-overflow: ellipsis` cuando no cabe; si cabe o no depende del ancho de la ventana, de la
// fuente que acabó cargando y de cuántas columnas armó la rejilla — cosas que el servidor no sabe.
// Antes esto se resolvía recortando la línea en Python con un tope de cinco cifras, y el resultado
// era peor por los dos lados: en pantalla ancha sobraba sitio y se había tirado dato igual, y en una
// estrecha seguía sin caber.
//
// `title` y no un tooltip propio: sale en cualquier navegador, no pide CSS y lo lee un lector de
// pantalla. La contrapartida es que en un teléfono no hay hover — pero ahí la caja es más ancha
// (una sola columna) y es justo donde la línea SÍ cabe entera.
//
// Se vuelve a mirar al cambiar el tamaño porque el corte cambia con él: al ensanchar la ventana una
// línea deja de estar cortada, y quedarse con el `title` puesto sería prometer algo que ya se ve.
(function () {
  function revisar() {
    document.querySelectorAll(".dgl-destacado-linea").forEach(function (linea) {
      // Un píxel de margen: los anchos son fraccionarios y comparar exacto marca como cortadas
      // líneas que entran justas.
      if (linea.scrollWidth > linea.clientWidth + 1) {
        linea.setAttribute("title", linea.textContent.trim());
      } else {
        linea.removeAttribute("title");
      }
    });
  }

  var pendiente;
  window.addEventListener("resize", function () {
    clearTimeout(pendiente);
    pendiente = setTimeout(revisar, 150);
  });
  // `load` y no `DOMContentLoaded`: con las fuentes todavía sin cargar los anchos son los de la
  // tipografía de reserva, y la medida saldría de otra letra que la que se va a leer.
  window.addEventListener("load", revisar);
})();
