/* La elección de tamaño del hueco horizontal — QA-02 del review v13.
 *
 * POR QUÉ ESTE ARCHIVO ES DE DINERO Y NO DE MAQUETACIÓN
 * -----------------------------------------------------
 * Cada `src` que se le pone a un marco es UNA IMPRESIÓN que Revive le factura al anunciante. Así que
 * los errores de este script no se ven como un fallo: se ven como un informe. Uno de más y a Adcio se
 * le cobra un anuncio que nadie vio; uno de menos y hay una franja de pantalla sin publicidad que
 * tampoco reclama nadie.
 *
 * Ya pasaron los dos. La primera versión dibujaba los tres tamaños y ocultaba dos con `display:none`
 * dando por hecho que un marco oculto no carga —es falso, se comprobó en el navegador—, o sea el
 * triple de impresiones. Y al montar líderes la etiqueta decía 992 mientras `.dgl-col-torre` empieza
 * en 1200, así que entre medias la torre se cargaba escondida.
 *
 * Ninguno de los dos se ve mirando el sitio. Salen en la factura, semanas después.
 *
 * LO QUE HAY QUE FALSEAR EN JSDOM, Y POR QUÉ NO LO INVALIDA
 * ---------------------------------------------------------
 * `clientWidth` es siempre 0 en jsdom, porque no maqueta nada. Se define a mano en el contenedor: lo
 * que se prueba es la DECISIÓN a partir de un ancho, no que el navegador mida bien — de eso ya se
 * encarga el navegador.
 */
import { readFileSync } from "node:fs";
import { beforeEach, describe, expect, it } from "vitest";

const FUENTE = readFileSync("static/js/anuncios.js", "utf8");

const SERVIDOR = "https://promo.dominicanosengrandesligas.com/www/pauta/dgl-m.php";

/* Los tres tamaños tal como los emite `anuncio_horizontal`, con sus pantallas mínimas. Los cortes
 * salen de medir el `.container` de Bootstrap en el sitio real: a 992-1199 px el contenedor mide 960
 * y un banner de 970 se saldría, por eso el corte del grande está en 1200 y no en 994. */
const HORIZONTAL = [
  { min: 1200, ancho: 970, alto: 90, url: `${SERVIDOR}?cb=aaa&zoneid=1` },
  { min: 992, ancho: 728, alto: 90, url: `${SERVIDOR}?cb=bbb&zoneid=2` },
  { min: 0, ancho: 320, alto: 50, url: `${SERVIDOR}?cb=ccc&zoneid=3` },
];

function pantalla(ancho) {
  window.innerWidth = ancho;
}

/** Un hueco dentro de un contenedor de `anchoContenedor` px. */
function poner(opciones, anchoContenedor) {
  document.body.innerHTML = `<div id="caja"><iframe class="dgl-ad-marco" data-anuncio='${JSON.stringify(
    opciones
  )}'></iframe></div>`;
  const caja = document.getElementById("caja");
  Object.defineProperty(caja, "clientWidth", { value: anchoContenedor, configurable: true });
  return caja.querySelector("iframe");
}

function correr() {
  new Function(FUENTE)();
}

/** La zona que se pidió de verdad, o `null` si el marco no pidió nada. */
function zonaPedida(marco) {
  if (!marco.isConnected || !marco.getAttribute("src")) return null;
  return new URL(marco.src).searchParams.get("zoneid");
}

describe("qué tamaño se pide", () => {
  it("pide el de 970 en escritorio ancho", () => {
    pantalla(1400);
    const marco = poner(HORIZONTAL, 1140);

    correr();

    expect(zonaPedida(marco)).toBe("1");
  });

  it("pide el de 728 en la franja donde el contenedor de Bootstrap mide 960", () => {
    /* LA FRANJA DE LOS PORTÁTILES DE 13 PULGADAS. La ventana da de sobra para un banner de 970, pero
     * el contenedor no: entre 992 y 1199 mide 960. Mirar `window.innerWidth` en vez del contenedor
     * habría sacado el banner grande fuera del contenido. */
    pantalla(1100);
    const marco = poner(HORIZONTAL, 960);

    correr();

    expect(zonaPedida(marco)).toBe("2");
  });

  it("pide el de teléfono en un teléfono", () => {
    pantalla(390);
    const marco = poner(HORIZONTAL, 358);

    correr();

    expect(zonaPedida(marco)).toBe("3");
  });

  it("no pide el grande aunque quepa, si la pantalla no llega a su mínimo", () => {
    /* El `min` es la REGLA DE NEGOCIO —ese formato se vende para escritorio— y el ancho real es la
     * comprobación. Si mandara solo el ancho, un contenedor suelto en una tablet pediría un banner de
     * escritorio y la zona de Revive dejaría de significar lo que dice el informe. */
    pantalla(800);
    const marco = poner(HORIZONTAL, 1200);

    correr();

    expect(zonaPedida(marco)).toBe("3");
  });
});

describe("los huecos que solo existen en un rango", () => {
  const TORRE = [{ min: 1200, ancho: 300, alto: 600, url: `${SERVIDOR}?cb=d&zoneid=9` }];
  const MOVIL = [{ min: 0, max: 991, ancho: 320, alto: 50, url: `${SERVIDOR}?cb=e&zoneid=8` }];

  it("la torre de escritorio no pide nada en un teléfono, aunque el CSS la esconda", () => {
    /* NO BASTA CON `d-none`: un `iframe` oculto SÍ carga su documento —comprobado en el navegador—,
     * así que esconderlo dejaría a Revive contando una impresión que nadie vio. */
    pantalla(390);
    const marco = poner(TORRE, 358);

    correr();

    expect(zonaPedida(marco)).toBe(null);
  });

  it("el banner de móvil no pide nada en escritorio", () => {
    pantalla(1400);
    const marco = poner(MOVIL, 1140);

    correr();

    expect(zonaPedida(marco)).toBe(null);
  });

  it("y el hueco desaparece del DOM en vez de quedarse vacío", () => {
    /* Dejarlo sin `src` no alcanza: el CSS le reserva el alto, así que quedaría una franja en blanco.
     * Es exactamente el whitespace que hubo que perseguir a mano en la portada. */
    pantalla(390);
    const marco = poner(TORRE, 358);

    correr();

    expect(marco.isConnected).toBe(false);
  });
});

describe("una impresión por hueco, ni una más", () => {
  it("no vuelve a pedir si el script corre dos veces", () => {
    /* Pasaría con un `htmx`, un `turbo` o un segundo `<script>` duplicado por descuido en el `base`.
     * El segundo `src` es otra línea en la factura del anunciante, no un fallo visible. */
    pantalla(1400);
    const marco = poner(HORIZONTAL, 1140);
    correr();
    const primera = marco.src;

    correr();

    expect(marco.src).toBe(primera);
  });

  it("no vuelve a pedir al cambiar el tamaño de la ventana", () => {
    /* Quien gire el teléfono se queda con el tamaño que le tocó al cargar. Se ve algo apretado, y es
     * preferible a cobrarle a Adcio por cada vez que alguien arrastra el borde de la ventana. */
    pantalla(1400);
    const marco = poner(HORIZONTAL, 1140);
    correr();
    const primera = marco.src;

    pantalla(390);
    window.dispatchEvent(new window.Event("resize"));

    expect(marco.src).toBe(primera);
  });

  it("monta cada hueco de la página, no solo el primero", () => {
    /* Toda página lleva al menos dos: el de arriba y el del pie. Un `querySelector` en vez de
     * `querySelectorAll` dejaría el segundo vacío para siempre. */
    pantalla(1400);
    document.body.innerHTML = `
      <div id="a"><iframe class="dgl-ad-marco" data-anuncio='${JSON.stringify(HORIZONTAL)}'></iframe></div>
      <div id="b"><iframe class="dgl-ad-marco" data-anuncio='${JSON.stringify(HORIZONTAL)}'></iframe></div>`;
    for (const id of ["a", "b"]) {
      Object.defineProperty(document.getElementById(id), "clientWidth", { value: 1140 });
    }

    correr();

    expect([...document.querySelectorAll("iframe")].every((m) => m.src)).toBe(true);
  });
});

describe("lo que no debe tumbar la página", () => {
  it("un atributo con JSON roto se ignora sin reventar", () => {
    /* Se serializa desde Django, así que hoy es válido siempre. Pero un `|escape` de más en la
     * plantilla lo rompería, y una excepción acá cortaría TODO el script — incluidos los huecos que
     * sí estaban bien. */
    pantalla(1400);
    document.body.innerHTML = `<div id="caja"><iframe class="dgl-ad-marco" data-anuncio="{roto"></iframe></div>`;
    Object.defineProperty(document.getElementById("caja"), "clientWidth", { value: 1140 });

    expect(() => correr()).not.toThrow();
    expect(document.querySelector("iframe").getAttribute("src")).toBe(null);
  });

  it("una lista vacía deja el hueco quieto, sin pedir y sin quitarlo", () => {
    pantalla(1400);
    const marco = poner([], 1140);

    correr();

    expect(marco.isConnected).toBe(true);
    expect(marco.getAttribute("src")).toBe(null);
  });

  it("sin servidor de anuncios no se pide nada", () => {
    /* Es el estado por defecto: `ADSERVER_URL` vacío. La opción llega sin `url` y el marco se queda
     * como está — el recuadro de maqueta lo pone la plantilla, no esto. */
    pantalla(1400);
    const marco = poner([{ min: 0, ancho: 970, alto: 90 }], 1140);

    correr();

    expect(marco.getAttribute("src")).toBe(null);
  });
});

describe("el hueco queda con la medida que se pidió", () => {
  it("pone ancho y alto del tamaño elegido", () => {
    /* Sin esto el marco se queda con el alto que le puso el CSS y el anuncio sale recortado o
     * flotando en un hueco más grande. */
    pantalla(1100);
    const marco = poner(HORIZONTAL, 960);

    correr();

    expect([marco.width, marco.height]).toEqual(["728", "90"]);
  });
});

beforeEach(() => {
  document.body.innerHTML = "";
  window.innerWidth = 1024;
});
