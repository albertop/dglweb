// El widget de líderes: cinco filas de cajas, y las dos expansiones que flotan sin empujar nada.
//
// Las pestañas NO están acá: las mueve `pestanas.js`, que es común a este widget y al de destacados.
// Este archivo solo escucha `dgl:pestana` para volver a su estado de llegada.
//
// Todo el contenido viene ya en el HTML —son unas treinta filas— y acá solo se muestra u oculta. Sin
// JavaScript la página sigue sirviendo: se ve la primera pestaña con el líder de cada categoría, que
// es información correcta, solo que menos.
(function () {
  var caja = document.querySelector('.dgl-lideres');
  if (!caja) return;

  var listas = Array.prototype.slice.call(caja.querySelectorAll('.dgl-lideres-lista'));

  // ── Cinco filas, y el resto flotando por encima ──────────────────────────────────────────────
  //
  // Cuántas cajas son cinco filas depende de cuántas columnas armó la retícula —dos en escritorio,
  // una en móvil— así que se mide en vez de contarse: las cajas de una misma fila comparten
  // `offsetTop`, y se corta después del tercer valor distinto.
  // Cinco filas en escritorio y cuatro en móvil, como los otros tres paneles de la franja. El número
  // tiene que decir lo mismo que el alto del marco en `site.css`: si se separan, o sobra sitio en
  // blanco o se recorta una fila que el botón cree estar enseñando.
  //
  // Se lee al arrancar y no se vuelve a mirar. Girar el teléfono cruzando los 992px dejaría el corte
  // viejo hasta la siguiente recarga, y es un caso que no compensa la complejidad de escucharlo: el
  // que gira una tablet ve una fila de más o de menos, no un widget roto.
  var FILAS = window.matchMedia('(min-width: 992px)').matches ? 5 : 4;
  var marco = caja.querySelector('.dgl-lideres-marco');
  var verTodas = caja.querySelector('.dgl-lideres-mas');
  var desplegado = false;

  function cajasDe(lista) {
    return Array.prototype.slice.call(lista.querySelectorAll('.dgl-lider-caja'));
  }

  function sobran(lista) {
    // Se miden con todas visibles; si no, la segunda pasada vería solo las que quedaron.
    var todas = cajasDe(lista);
    todas.forEach(function (c) { c.classList.remove('dgl-fila-de-mas'); });

    var tops = [];
    return todas.filter(function (c) {
      var top = c.offsetTop;
      if (tops.indexOf(top) === -1) tops.push(top);
      return tops.length > FILAS;
    });
  }

  function activa() {
    return listas.filter(function (l) { return !l.classList.contains('d-none'); })[0];
  }

  function recortar() {
    // El guardia no es de adorno: `mostrar()` llama a esto en cada cambio de pestaña, y sin el
    // botón —una lista corta que cabe entera— no habría nada que actualizar.
    if (desplegado || !verTodas || !marco) return;
    var enLaActiva = 0;

    listas.forEach(function (lista) {
      // Una lista escondida mide cero y todas sus cajas comparten `offsetTop`, así que se muestra un
      // instante para medirla de verdad. Con `visibility` puesta, para que el salto no se vea.
      var oculta = lista.classList.contains('d-none');
      if (oculta) { lista.style.visibility = 'hidden'; lista.classList.remove('d-none'); }

      var demas = sobran(lista);
      demas.forEach(function (c) { c.classList.add('dgl-fila-de-mas'); });
      if (!oculta) enLaActiva = demas.length;

      if (oculta) { lista.classList.add('d-none'); lista.style.visibility = ''; }
    });

    // El botón habla de la pestaña que se está viendo: bateo tiene catorce categorías y pitcheo
    // cinco, así que «ver 8 más» sería falso en una de las dos si se contaran juntas.
    //
    // Cuando no hay nada más se apaga pero NO se quita: sigue ocupando su renglón, para que el widget
    // mida igual en la pestaña que lo lleva y en la que no.
    verTodas.classList.toggle('esta-de-mas', enLaActiva === 0);
    // Espacio duro y no cadena vacía: un botón sin texto no tiene alto de línea, así que al pasar a
    // la pestaña que no lo necesita el widget encogía unos píxeles. `visibility` lo esconde, pero
    // solo reserva el sitio si hay algo que medir.
    verTodas.textContent = enLaActiva ? 'ver ' + enLaActiva + ' más' : ' ';
  }

  function cerrar() {
    if (!verTodas || !marco) return;
    desplegado = false;
    caja.classList.remove('is-desplegado');
    listas.forEach(function (l) { l.classList.remove('is-flotante'); });
    verTodas.setAttribute('aria-expanded', 'false');
    recortar();
  }

  function abrir() {
    // No hace falta congelar el alto del marco: lo fija el CSS en tres filas exactas, así que al
    // soltar la lista a flotar el hueco se queda igual y nada de abajo se mueve.
    desplegado = true;
    caja.classList.add('is-desplegado');
    cajasDe(activa()).forEach(function (c) { c.classList.remove('dgl-fila-de-mas'); });
    activa().classList.add('is-flotante');
    verTodas.setAttribute('aria-expanded', 'true');
    verTodas.textContent = 'ver menos';
  }

  // El «Cerrar» del final de la capa. Va delegado y no uno por lista: hay una lista por oficio y
  // todas llevan el suyo, así que enganchar uno por uno obligaría a recorrerlas y a acordarse de la
  // que se añada mañana.
  caja.addEventListener('click', function (evento) {
    if (evento.target.closest('[data-cerrar-lideres]')) cerrar();
  });

  if (verTodas && marco) {
    recortar();
    verTodas.addEventListener('click', function () {
      if (desplegado) { cerrar(); } else { abrir(); }
    });
    // Cambiar de oficio devuelve el widget a como se ve al llegar: tres filas y ninguna capa abierta.
    // Heredar lo abierto de la otra pestaña dejaría una capa flotando sobre un contenido que ya no es
    // el suyo, y un «ver menos» hablando de una lista que el lector ya no está mirando.
    caja.addEventListener('dgl:pestana', function () { cerrarCajas(null); cerrar(); });
    // Un clic fuera y Escape lo cierran: es una capa que tapa contenido, y quedarse sin salida
    // evidente es lo que hace que una capa moleste.
    document.addEventListener('click', function (e) {
      if (desplegado && !caja.contains(e.target)) cerrar();
    });
    document.addEventListener('keydown', function (e) {
      if (desplegado && e.key === 'Escape') { cerrar(); verTodas.focus(); }
    });
    // La retícula cambia de columnas al cambiar el ancho, así que el corte hay que rehacerlo.
    var temporizador;
    window.addEventListener('resize', function () {
      clearTimeout(temporizador);
      temporizador = setTimeout(function () { if (!desplegado) recortar(); }, 150);
    });
  }

  // ── El «ver más» de cada caja ───────────────────────────────────────────────────────────────
  // La capa de una caja cuelga de su borde inferior y tapa lo que hay debajo: nada se empuja, así
  // que ninguna otra caja cambia de sitio bajo el cursor de quien acaba de hacer clic.
  //
  // Una sola abierta a la vez, por lo mismo que la capa flota: dos capas superpuestas taparían la
  // segunda con la primera.
  //
  // Un solo escucha en el contenedor en vez de uno por botón: son hasta diecinueve cajas por
  // pestaña, y el que decide es el botón donde se hizo clic.
  function cerrarCajas(salvo) {
    Array.prototype.forEach.call(caja.querySelectorAll('.dgl-lider-caja.is-abierta'), function (c) {
      if (c === salvo) return;
      c.classList.remove('is-abierta');
      c.querySelector('.dgl-lider-extra').classList.add('d-none');
      var b = c.querySelector('.dgl-lider-mas');
      b.setAttribute('aria-expanded', 'false');
      b.textContent = 'ver ' + c.querySelectorAll('.dgl-lider-extra .dgl-lider').length + ' más';
    });
  }

  caja.addEventListener('click', function (e) {
    var boton = e.target.closest('.dgl-lider-mas');
    if (!boton) return;

    var suCaja = boton.closest('.dgl-lider-caja');
    var extra = suCaja.querySelector('.dgl-lider-extra');
    var abierto = boton.getAttribute('aria-expanded') === 'true';

    cerrarCajas(suCaja);
    extra.classList.toggle('d-none', abierto);
    suCaja.classList.toggle('is-abierta', !abierto);
    boton.setAttribute('aria-expanded', abierto ? 'false' : 'true');
    boton.textContent = abierto ? 'ver ' + extra.querySelectorAll('.dgl-lider').length + ' más' : 'ver menos';
  });

  // Un clic fuera y Escape también cierran la capa de una caja, por lo mismo que la del widget: una
  // capa que tapa contenido y no tiene salida evidente molesta.
  document.addEventListener('click', function (e) {
    if (!e.target.closest('.dgl-lider-caja')) cerrarCajas(null);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') cerrarCajas(null);
  });
})();
