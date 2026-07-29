/* El teclado del buscador de jugadores — FE-02 del review v6.
 *
 * QUÉ SE PROTEGE, Y POR QUÉ ESTO Y NO OTRA COSA
 * ---------------------------------------------
 * El buscador es una MEJORA sobre un formulario que funciona sin JavaScript. Toda su lógica de
 * teclado consiste en decidir cuándo interceptar una tecla y cuándo dejarla pasar, y ahí está el
 * fallo que ninguna prueba veía:
 *
 *   Enter CON una sugerencia resaltada  →  se intercepta y se navega a ese jugador.
 *   Enter SIN nada resaltado            →  NO se toca, y el formulario hace su GET de siempre.
 *
 * Invertir esa condición —un cambio de un carácter— rompe el segundo caso, y no se ve mirando la
 * pantalla: la caja sigue ahí, la lista sigue ahí, y escribir «soto» y pulsar Enter simplemente no
 * hace nada. Es el tipo de fallo que un usuario no reporta porque asume que hizo algo mal.
 *
 * CÓMO SE CARGA EL SCRIPT
 * -----------------------
 * `buscador.js` es una función que se ejecuta sola al cargarse y se monta sobre lo que encuentre en
 * el DOM en ese instante. Por eso se lee del disco y se evalúa DESPUÉS de armar el DOM de cada
 * prueba, en vez de importarlo: un `import` se cachea, y la segunda prueba se montaría sobre el DOM
 * de la primera.
 */
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Ruta relativa a la raíz del proyecto y no `import.meta.url`: bajo el entorno `jsdom`, `vitest`
// sirve el módulo con una URL que no es `file:`, y `readFileSync` la rechaza. `vitest` siempre corre
// desde la raíz, así que esto es estable.
const FUENTE = readFileSync("static/js/buscador.js", "utf8");

const RESPUESTA = {
  results: [
    { slug: "juan-soto-665742", name: "Juan Soto", pos: "OF", span: "2018-2026" },
    { slug: "pedro-martinez-118377", name: "Pedro Martínez", pos: "P", span: "1992-2009" },
    { slug: "sammy-sosa-122544", name: "Sammy Sosa", pos: "OF", span: "1989-2007" },
  ],
  hidden: 0,
};

/** Arma la caja, monta el script y deja las sugerencias ya pintadas. */
async function buscador(respuesta = RESPUESTA) {
  document.body.innerHTML = `
    <form action="/jugadores/">
      <div class="position-relative">
        <input id="buscar" name="q" data-buscador="/api/sugerencias/" data-minimo="2">
      </div>
    </form>`;

  global.fetch = vi.fn(() => Promise.resolve({ json: () => Promise.resolve(respuesta) }));
  new Function(FUENTE)();

  const caja = document.getElementById("buscar");
  caja.value = "so";
  caja.dispatchEvent(new Event("input"));

  // El debounce son 150 ms y el `fetch` resuelve en microtareas: hay que soltar las dos cosas.
  await vi.advanceTimersByTimeAsync(200);

  return { caja, lista: document.querySelector(".dgl-sugerencias") };
}

function pulsar(caja, key) {
  const evento = new window.KeyboardEvent("keydown", { key, bubbles: true, cancelable: true });
  caja.dispatchEvent(evento);
  return evento;
}

const resaltada = (lista) => lista.querySelector(".activo");

beforeEach(() => {
  vi.useFakeTimers();
  // `window.location` es de solo lectura en jsdom; el script escribe `href` para navegar.
  delete window.location;
  window.location = { href: "" };
  // `jsdom` no implementa `scrollIntoView` —no hay viewport que desplazar— y el script lo llama al
  // resaltar una sugerencia. Sin este relleno, cada flecha lanza una excepción dentro del listener:
  // las pruebas pasaban igual, pero la corrida escupía trece errores que enterraban cualquier fallo
  // de verdad. Un corredor ruidoso deja de leerse, igual que un log ruidoso.
  window.Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("las flechas", () => {
  it("bajan por la lista y vuelven al principio al pasarse", async () => {
    const { caja, lista } = await buscador();

    pulsar(caja, "ArrowDown");
    expect(resaltada(lista).textContent).toContain("Juan Soto");

    pulsar(caja, "ArrowDown");
    pulsar(caja, "ArrowDown");
    expect(resaltada(lista).textContent).toContain("Sammy Sosa");

    // La cuarta da la vuelta en vez de quedarse clavada en la última.
    pulsar(caja, "ArrowDown");
    expect(resaltada(lista).textContent).toContain("Juan Soto");
  });

  it("hacia arriba desde nada empiezan por la última", async () => {
    const { caja, lista } = await buscador();

    pulsar(caja, "ArrowUp");

    expect(resaltada(lista).textContent).toContain("Sammy Sosa");
  });

  it("solo dejan una resaltada a la vez", async () => {
    const { caja, lista } = await buscador();

    pulsar(caja, "ArrowDown");
    pulsar(caja, "ArrowDown");

    expect(lista.querySelectorAll(".activo")).toHaveLength(1);
    expect(lista.querySelectorAll('[aria-selected="true"]')).toHaveLength(1);
  });

  it("no se paran en la fila de «ver todos», que no es un jugador", async () => {
    const { caja, lista } = await buscador({ ...RESPUESTA, hidden: 65 });
    expect(lista.querySelector(".dgl-sugerencias-mas")).not.toBeNull();

    // Cuatro bajadas con tres jugadores: si la fila de «más» contara, la cuarta caería en ella.
    for (let i = 0; i < 4; i++) pulsar(caja, "ArrowDown");

    expect(resaltada(lista).getAttribute("role")).toBe("option");
    expect(resaltada(lista).textContent).toContain("Juan Soto");
  });
});

describe("Enter", () => {
  it("con una sugerencia resaltada va a ese jugador", async () => {
    const { caja } = await buscador();
    pulsar(caja, "ArrowDown");

    const evento = pulsar(caja, "Enter");

    expect(window.location.href).toBe("/jugador/juan-soto-665742/");
    expect(evento.defaultPrevented).toBe(true);
  });

  it("SIN nada resaltado deja pasar la tecla para que el formulario busque", async () => {
    // La prueba que motivó todo esto. Si el script se quedara con este Enter, escribir un nombre y
    // pulsar Enter no haría nada — y el buscador seguiría en pantalla como si funcionara.
    const { caja } = await buscador();

    const evento = pulsar(caja, "Enter");

    expect(evento.defaultPrevented).toBe(false);
    expect(window.location.href).toBe("");
  });
});

describe("Escape", () => {
  it("cierra la lista y suelta el resaltado", async () => {
    const { caja, lista } = await buscador();
    pulsar(caja, "ArrowDown");

    pulsar(caja, "Escape");

    expect(lista.classList.contains("d-none")).toBe(true);
    expect(caja.getAttribute("aria-expanded")).toBe("false");
    expect(caja.hasAttribute("aria-activedescendant")).toBe(false);
  });

  it("con la lista cerrada las teclas no hacen nada", async () => {
    const { caja, lista } = await buscador();
    pulsar(caja, "Escape");

    const evento = pulsar(caja, "ArrowDown");

    expect(evento.defaultPrevented).toBe(false);
    expect(resaltada(lista)).toBeNull();
  });
});

describe("lo que se le pide al servidor", () => {
  it("no pregunta por debajo del mínimo de letras", async () => {
    document.body.innerHTML = `<div class="position-relative">
      <input id="buscar" data-buscador="/api/sugerencias/" data-minimo="2"></div>`;
    global.fetch = vi.fn();
    new Function(FUENTE)();

    const caja = document.getElementById("buscar");
    caja.value = "s";
    caja.dispatchEvent(new Event("input"));
    await vi.advanceTimersByTimeAsync(200);

    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("hace UNA petición por pausa y no una por tecla", async () => {
    document.body.innerHTML = `<div class="position-relative">
      <input id="buscar" data-buscador="/api/sugerencias/" data-minimo="2"></div>`;
    global.fetch = vi.fn(() => Promise.resolve({ json: () => Promise.resolve(RESPUESTA) }));
    new Function(FUENTE)();

    const caja = document.getElementById("buscar");
    for (const texto of ["so", "sot", "soto"]) {
      caja.value = texto;
      caja.dispatchEvent(new Event("input"));
      await vi.advanceTimersByTimeAsync(50); // menos que el debounce: no llega a disparar
    }
    await vi.advanceTimersByTimeAsync(200);

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch.mock.calls[0][0]).toContain("q=soto");
  });
});

describe("las respuestas que llegan tarde — FE-01 del review v11", () => {
  /* EL FALLO, TAL COMO LO VIVE UN USUARIO
   * --------------------------------------
   * Escribe «so», la petición sale, y antes de que responda borra la caja. La lista se cierra, como
   * debe. Un instante después llega la respuesta y **la lista se reabre sola**, con sugerencias de
   * una búsqueda que ya no existe y con la caja vacía.
   *
   * El `debounce` no lo cubre y nunca podría: retrasa el DISPARO de la petición, pero no hay espera
   * que alcance a una respuesta que ya salió. La única defensa es invalidar el testigo al cerrar.
   *
   * Medido antes del arreglo: `lista oculta = false`, `aria-expanded = true`, 1 sugerencia pintada,
   * con la caja en «».
   *
   * CÓMO SE PRUEBA UNA CARRERA
   * ---------------------------
   * Con un `fetch` que devuelve una promesa que NO se resuelve sola: se guarda su `resolve` y se
   * llama a mano después de cerrar. Es la única forma de poner el «tarde» dentro de una prueba
   * determinista — con temporizadores el orden dependería de la máquina.
   */
  async function conRespuestaAplazada() {
    document.body.innerHTML = `
      <form action="/jugadores/">
        <div class="position-relative">
          <input id="buscar" name="q" data-buscador="/api/sugerencias/" data-minimo="2">
        </div>
      </form>`;

    let responder;
    const aplazada = new Promise((r) => {
      responder = r;
    });
    global.fetch = vi.fn(() => aplazada);
    new Function(FUENTE)();

    const caja = document.getElementById("buscar");
    caja.value = "so";
    caja.dispatchEvent(new Event("input"));
    await vi.advanceTimersByTimeAsync(200);
    expect(global.fetch).toHaveBeenCalledTimes(1);

    const lista = document.querySelector(".dgl-sugerencias");
    return {
      caja,
      lista,
      // Deja llegar la respuesta vieja.
      llega: async () => {
        responder({ json: () => Promise.resolve(RESPUESTA) });
        await vi.advanceTimersByTimeAsync(50);
      },
    };
  }

  it("borrar la caja mantiene la lista cerrada aunque la respuesta llegue después", async () => {
    const { caja, lista, llega } = await conRespuestaAplazada();

    caja.value = "";
    caja.dispatchEvent(new Event("input"));
    await vi.advanceTimersByTimeAsync(200);

    await llega();

    expect(lista.classList.contains("d-none")).toBe(true);
    expect(lista.children.length).toBe(0);
    // El estado ARIA importa tanto como lo visible: con `aria-expanded="true"` sobre una lista
    // vacía, un lector de pantalla anuncia sugerencias que no existen.
    expect(caja.getAttribute("aria-expanded")).toBe("false");
  });

  it("una búsqueda NUEVA sigue pintando lo suyo — el arreglo no puede romper el caso normal", async () => {
    const { caja, lista, llega } = await conRespuestaAplazada();

    caja.value = "";
    caja.dispatchEvent(new Event("input"));
    await vi.advanceTimersByTimeAsync(200);

    // El usuario escribe otra cosa y ESTA sí tiene que salir.
    global.fetch = vi.fn(() => Promise.resolve({ json: () => Promise.resolve(RESPUESTA) }));
    caja.value = "pedro";
    caja.dispatchEvent(new Event("input"));
    await vi.advanceTimersByTimeAsync(200);

    expect(lista.classList.contains("d-none")).toBe(false);
    expect(lista.children.length).toBe(RESPUESTA.results.length);

    // Y que llegue ahora la vieja no puede pisar a la nueva.
    await llega();
    expect(lista.children.length).toBe(RESPUESTA.results.length);
    expect(lista.classList.contains("d-none")).toBe(false);
  });
});
