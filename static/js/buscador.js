/* Buscador de jugadores con sugerencias mientras se escribe.
 *
 * Se monta solo sobre cualquier <input data-buscador="URL-del-endpoint">, así que el mismo código
 * sirve para la caja del header —presente en todas las páginas— y para la de /jugadores/. Antes esto
 * vivía dentro de la plantilla del índice y estaba atado a sus ids; sacarlo acá es lo que permite que
 * las dos cajas se comporten igual sin copiar nada.
 *
 * Es una MEJORA sobre el formulario, no un reemplazo. Cada caja vive dentro de un <form> que hace un
 * GET normal a /jugadores/, así que si este archivo no carga —o el usuario no tiene JavaScript—
 * escribir y pulsar Enter sigue llevando a la misma búsqueda, solo que renderizada por el servidor.
 */
(function () {
  "use strict";

  var ESPERA_MS = 150; // debounce: una petición por pausa, no una por tecla
  var MINIMO_POR_DEFECTO = 2;

  function montar(caja) {
    var endpoint = caja.dataset.buscador;
    if (!endpoint) return;

    // El servidor es el que manda sobre el mínimo (devuelve vacío por debajo de su umbral); esto solo
    // evita el viaje. Si los dos números se separan, lo peor que pasa es una petición de más.
    var minimo = parseInt(caja.dataset.minimo, 10) || MINIMO_POR_DEFECTO;

    // El desplegable se crea acá y no en la plantilla: así cada caja nueva es un atributo y no un
    // bloque de HTML que hay que acordarse de copiar con sus ids y su ARIA.
    var envoltorio = caja.parentElement;
    var lista = document.createElement("ul");
    lista.className = "dgl-sugerencias d-none";
    lista.id = (caja.id || "buscador") + "-sugerencias";
    lista.setAttribute("role", "listbox");
    lista.setAttribute("aria-label", "Sugerencias");
    envoltorio.appendChild(lista);

    caja.setAttribute("role", "combobox");
    caja.setAttribute("aria-expanded", "false");
    caja.setAttribute("aria-controls", lista.id);
    caja.setAttribute("aria-autocomplete", "list");
    caja.setAttribute("autocomplete", "off"); // el desplegable del navegador tapaba el nuestro

    var espera = null;
    var enVuelo = null; // la última petición, para descartar respuestas que llegan tarde
    var activo = -1;

    // Los resultados que pintó el SERVIDOR al cargar la página, si esta caja los declara. Dejan de
    // ser ciertos en cuanto se toca el texto, y un encabezado «Resultados para car» encima de una
    // caja donde ya dice «carlos m» es peor que no mostrar nada.
    var seccion = caja.dataset.resultados ? document.getElementById(caja.dataset.resultados) : null;
    var consultaInicial = caja.value.trim();

    function sincronizarSeccion() {
      // Comparar contra el texto original y no "ocultar para siempre": si el usuario borra lo que
      // escribió de más y vuelve a la consulta con la que llegó, la sección es válida otra vez.
      if (seccion) seccion.classList.toggle("d-none", caja.value.trim() !== consultaInicial);
    }

    function cerrar() {
      lista.classList.add("d-none");
      lista.innerHTML = "";
      caja.setAttribute("aria-expanded", "false");
      caja.removeAttribute("aria-activedescendant");
      activo = -1;
    }

    function ir(i) {
      var li = lista.children[i];
      if (li) window.location.href = li.dataset.url;
    }

    function pintar(datos) {
      var resultados = datos.results || [];
      if (!resultados.length) {
        cerrar();
        return;
      }
      lista.innerHTML = "";
      resultados.forEach(function (r, i) {
        // Todo por nodo y nada por interpolación de HTML: un nombre nunca se inyecta como marcado.
        var li = document.createElement("li");
        li.id = lista.id + "-op-" + i;
        li.setAttribute("role", "option");
        li.setAttribute("aria-selected", "false");
        li.dataset.url = "/jugador/" + r.slug + "/";

        var nombre = document.createElement("span");
        nombre.className = "nombre";
        nombre.textContent = r.name;

        var meta = document.createElement("span");
        meta.className = "dgl-meta";
        meta.textContent = (r.pos ? r.pos + " · " : "") + (r.span || "");

        li.appendChild(nombre);
        li.appendChild(meta);
        // `mousedown` y no `click`: el blur del input cierra la lista antes de que el click llegue.
        li.addEventListener("mousedown", function (e) {
          e.preventDefault();
          ir(i);
        });
        lista.appendChild(li);
      });

      // La fila que evita el peor fallo de un buscador: recortar sin decirlo. Con 68 «jose» en la
      // base, ver diez y ningún aviso lleva a concluir que los otros no existen. No es una opción
      // navegable con las flechas —no es un jugador— sino la puerta a la lista entera.
      if (datos.hidden > 0) {
        var mas = document.createElement("li");
        mas.className = "dgl-sugerencias-mas";
        mas.dataset.url = paginaDeResultados(caja.value.trim());
        mas.textContent = "y " + datos.hidden + " más — ver todos";
        mas.addEventListener("mousedown", function (e) {
          e.preventDefault();
          window.location.href = mas.dataset.url;
        });
        lista.appendChild(mas);
      }

      lista.classList.remove("d-none");
      caja.setAttribute("aria-expanded", "true");
      activo = -1;
    }

    function paginaDeResultados(texto) {
      return (caja.form ? caja.form.getAttribute("action") : "/jugadores/") + "?q=" + encodeURIComponent(texto);
    }

    function resaltar(delta) {
      // Solo las opciones: la fila de «y N más» no es un jugador y no debe recibir el foco.
      var n = lista.querySelectorAll('[role="option"]').length;
      if (!n) return;
      if (activo >= 0) {
        lista.children[activo].classList.remove("activo");
        lista.children[activo].setAttribute("aria-selected", "false");
      }
      activo += delta;
      if (activo < 0) activo = n - 1;
      if (activo >= n) activo = 0;
      var li = lista.children[activo];
      li.classList.add("activo");
      li.setAttribute("aria-selected", "true");
      caja.setAttribute("aria-activedescendant", li.id);
      li.scrollIntoView({ block: "nearest" });
    }

    caja.addEventListener("input", function () {
      var texto = caja.value.trim();
      sincronizarSeccion(); // antes del corte por longitud: vaciar la caja también la esconde
      clearTimeout(espera);
      if (texto.length < minimo) {
        cerrar();
        return;
      }
      espera = setTimeout(function () {
        var mio = {};
        enVuelo = mio;
        fetch(endpoint + "?q=" + encodeURIComponent(texto))
          .then(function (r) {
            return r.json();
          })
          .then(function (d) {
            if (enVuelo === mio) pintar(d);
          })
          .catch(cerrar); // sin sugerencias; el formulario sigue funcionando
      }, ESPERA_MS);
    });

    caja.addEventListener("keydown", function (e) {
      if (lista.classList.contains("d-none")) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        resaltar(1);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        resaltar(-1);
      } else if (e.key === "Enter" && activo >= 0) {
        // Solo si hay uno resaltado. Si no, deja pasar el Enter y el formulario hace su GET.
        e.preventDefault();
        ir(activo);
      } else if (e.key === "Escape") {
        cerrar();
      }
    });

    document.addEventListener("click", function (e) {
      if (!lista.contains(e.target) && e.target !== caja) cerrar();
    });
  }

  document.querySelectorAll("[data-buscador]").forEach(montar);
})();
