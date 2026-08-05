/* La ventana de «Un día como hoy»: cuántas tarjetas se ven, cuánto duran y qué hacen los controles.
 *
 * QUÉ SE PROTEGE
 * --------------
 * El servidor manda las dieciséis tarjetas SUELTAS y sin emparejar, justamente para que el móvil
 * pueda enseñar una sola a la vez. Eso deja tres cosas en el JavaScript que ningún test de Python
 * puede ver:
 *
 *   1. Que la ventana mida DOS en escritorio y UNA en móvil, con el mismo corte de 768px que el CSS.
 *      Si los dos se separan, el teléfono pinta dos tarjetas una encima de la otra.
 *   2. Que la duración sea la SUMA de lo que se ve, topada por `data-min` y `data-max`. El suelo y
 *      el techo son de la ventana, no de la tarjeta: dos cumpleaños seguidos no pueden costar veinte
 *      segundos entre los dos.
 *   3. Que no queden dos temporizadores vivos al pulsar «Próximo» mientras corre el reloj — eso hace
 *      que el widget empiece a saltarse pantallas de dos en dos.
 */
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const FUENTE = readFileSync("static/js/dia_como_hoy.js", "utf8");

const MIN = 10000;
const MAX = 24000;

/* `matchMedia` no existe en jsdom. Se finge, y devolviendo lo que la consulta pida:
 * `(min-width: 768px)` según el ancho que se le pase, y `prefers-reduced-motion` siempre en falso
 * salvo que la prueba diga lo contrario. */
function fingirMedios({ ancha = true, quieto = false } = {}) {
  window.matchMedia = vi.fn((consulta) => ({
    matches: consulta.includes("prefers-reduced-motion") ? quieto : ancha,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
}

/** `cuantas` tarjetas, cada una con la duración que se le diga (por defecto 6 s). */
function montar(cuantas, ms = 6000) {
  const tarjetas = Array.from({ length: cuantas }, (_, i) => {
    const duracion = Array.isArray(ms) ? ms[i] : ms;
    const primera = i === 0 ? " es-primera" : i === 1 ? " es-segunda" : "";
    return `<article class="dgl-dch-caja${primera}" data-ms="${duracion}">${i}</article>`;
  }).join("");
  document.body.innerHTML = `
    <div class="dgl-dch" id="dia-como-hoy" data-min="${MIN}" data-max="${MAX}">${tarjetas}</div>
    <div class="dgl-dch-controles" hidden>
      <button type="button" class="dgl-pill" data-dch-mover="-1">Anterior</button>
      <div class="dgl-dch-puntos"></div>
      <span class="dgl-dch-cuenta"></span>
      <button type="button" class="dgl-pill" data-dch-mover="1">Próximo</button>
    </div>`;
}

function visibles() {
  return Array.from(document.querySelectorAll(".dgl-dch-caja.es-visible")).map((t) => t.textContent);
}

function arrancar() {
  new Function(FUENTE)();
}

describe("«Un día como hoy»", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    fingirMedios();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  it("enseña dos tarjetas a la vez en escritorio", () => {
    montar(6);
    arrancar();

    expect(visibles()).toEqual(["0", "1"]);
    expect(document.querySelectorAll(".dgl-dch-punto")).toHaveLength(3);
  });

  it("enseña UNA sola en móvil, que es de lo que se trata el corte de 768px", () => {
    fingirMedios({ ancha: false });
    montar(6);
    arrancar();

    expect(visibles()).toEqual(["0"]);
    // Dieciséis pantallas de puntos no se pulsan en un teléfono: el CSS los esconde y deja la
    // cuenta. El JavaScript los dibuja igual porque quien decide qué se ve es la hoja de estilo.
    expect(document.querySelector(".dgl-dch-cuenta").textContent).toBe("1 / 6");
  });

  it("rota sola al cabo de lo que dura la ventana", () => {
    montar(4, 6000);
    arrancar();

    // 6000 + 6000 = 12000, entre el suelo y el techo.
    vi.advanceTimersByTime(11999);
    expect(visibles()).toEqual(["0", "1"]);
    vi.advanceTimersByTime(1);
    expect(visibles()).toEqual(["2", "3"]);
  });

  it("suma lo que se ve y aplica el suelo, no la cuenta de cada tarjeta", () => {
    // Dos cumpleaños: 1500 cada uno. Sumados son 3000, por debajo del suelo — y el suelo se aplica
    // UNA vez a la ventana, no dos veces a las tarjetas.
    montar(4, [1500, 1500, 6000, 6000]);
    arrancar();

    vi.advanceTimersByTime(MIN - 1);
    expect(visibles()).toEqual(["0", "1"]);
    vi.advanceTimersByTime(1);
    expect(visibles()).toEqual(["2", "3"]);
  });

  it("aplica el techo cuando las dos traen mucho texto", () => {
    montar(4, [20000, 20000, 6000, 6000]);
    arrancar();

    vi.advanceTimersByTime(MAX - 1);
    expect(visibles()).toEqual(["0", "1"]);
    vi.advanceTimersByTime(1);
    expect(visibles()).toEqual(["2", "3"]);
  });

  it("«Próximo» adelanta y «Anterior» atrasa aunque esté rotando sola", () => {
    montar(6);
    arrancar();

    document.querySelector('[data-dch-mover="1"]').click();
    expect(visibles()).toEqual(["2", "3"]);
    document.querySelector('[data-dch-mover="-1"]').click();
    expect(visibles()).toEqual(["0", "1"]);
  });

  it("«Anterior» desde la primera da la vuelta a la última", () => {
    montar(6);
    arrancar();

    document.querySelector('[data-dch-mover="-1"]').click();

    // El `%` de JavaScript con negativos devuelve negativo; sin normalizar, esto no enseñaba nada.
    expect(visibles()).toEqual(["4", "5"]);
  });

  it("no deja dos temporizadores vivos al pulsar mientras corre el reloj", () => {
    montar(6);
    arrancar();

    vi.advanceTimersByTime(3000); // a medio camino de los 12 s de la ventana
    document.querySelector('[data-dch-mover="1"]').click();
    expect(visibles()).toEqual(["2", "3"]);

    // Si quedara vivo el temporizador de antes, a los 9 s restantes saltaría otra vez.
    vi.advanceTimersByTime(9000);
    expect(visibles()).toEqual(["2", "3"]);
    // Y la ventana nueva cumple sus 12 s enteros desde el clic, no lo que quedaba de la anterior.
    vi.advanceTimersByTime(3000);
    expect(visibles()).toEqual(["4", "5"]);
  });

  it("se para con el ratón encima y sigue al salir", () => {
    montar(6);
    arrancar();

    document.getElementById("dia-como-hoy").dispatchEvent(new Event("mouseenter"));
    vi.advanceTimersByTime(60000);
    expect(visibles()).toEqual(["0", "1"]);

    document.getElementById("dia-como-hoy").dispatchEvent(new Event("mouseleave"));
    vi.advanceTimersByTime(12000);
    expect(visibles()).toEqual(["2", "3"]);
  });

  it("esconde los controles cuando no hay a dónde ir", () => {
    // Dos tarjetas en escritorio son UNA pantalla. Unas flechas que no mueven nada son un botón roto.
    montar(2);
    arrancar();

    expect(document.querySelector(".dgl-dch-controles").hidden).toBe(true);
  });

  it("con «prefers-reduced-motion» no arranca ni destapa los controles", () => {
    fingirMedios({ quieto: true });
    montar(6);
    arrancar();

    vi.advanceTimersByTime(60000);
    // El CSS las enseña las seis apiladas; acá lo que se comprueba es que el reloj no corrió y que
    // las clases de «sin JavaScript» siguen intactas.
    expect(visibles()).toEqual([]);
    expect(document.querySelector(".dgl-dch-controles").hidden).toBe(true);
    expect(document.querySelector(".es-primera")).not.toBeNull();
  });
});
