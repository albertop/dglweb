/* El ciclo de vida de los listeners de la pizarra — DEV-01/QA-01/FE-01 del review v9.
 *
 * QUÉ SE PROTEGE
 * --------------
 * La pizarra se refresca sola cada minuto cuando hay juegos vivos, y lo hace reemplazando el
 * `outerHTML` del banner entero y volviendo a llamar a `preparar()`. Antes de este arreglo,
 * `preparar()` registraba OTRO `document.addEventListener("click", …)` cerrado sobre el banner de
 * esa versión: una hora de juegos en vivo dejaba sesenta handlers, cincuenta y nueve de ellos
 * apuntando a nodos ya desprendidos del documento.
 *
 * No rompía la primera interacción —por eso nadie lo vio— y degradaba con el tiempo, justo cuando
 * más tráfico hay.
 *
 * ESTA PRUEBA PASA POR EL CAMINO REAL, no por un atajo: monta con `data-vivo="1"`, simula el
 * `fetch` y adelanta el reloj, así que el refresco ejecuta `preparar()` de verdad. Reemplazar el
 * HTML a mano habría dejado pasar una regresión que volviera a meter el listener ahí dentro.
 */
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const FUENTE = readFileSync("static/js/pizarra.js", "utf8");

const BANNER = `
  <section id="pizarra" class="dgl-pizarra" data-vivo="1">
    <div class="dgl-tira">
      <article class="dgl-juego" tabindex="0">
        <div class="dgl-juego-detalle" hidden>algo</div>
      </article>
    </div>
  </section>`;

function clicsRegistrados(espia) {
  return espia.mock.calls.filter(([tipo]) => tipo === "click").length;
}

describe("los listeners de documento de la pizarra", () => {
  let espia;

  beforeEach(() => {
    vi.useFakeTimers();
    document.body.innerHTML = BANNER;
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, text: () => Promise.resolve(BANNER) }));
    espia = vi.spyOn(document, "addEventListener");
    new Function(FUENTE)();
    // El script se engancha a `DOMContentLoaded`, que en jsdom ya pasó cuando corre la prueba.
    document.dispatchEvent(new Event("DOMContentLoaded"));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  it("registra UNO solo de click, por muchos refrescos que pasen", async () => {
    const alMontar = clicsRegistrados(espia);

    // Tres refrescos en vivo por el camino de verdad: cada uno reemplaza el banner y llama a
    // `preparar()`. `CADA` es un minuto, y el `fetch` resuelve en microtareas.
    for (let i = 0; i < 3; i++) {
      await vi.advanceTimersByTimeAsync(61_000);
    }

    expect(alMontar).toBe(1);
    expect(clicsRegistrados(espia)).toBe(1);
    expect(global.fetch).toHaveBeenCalledTimes(3);
  });

  it("un clic fuera sigue funcionando después de un refresco", async () => {
    const viejo = document.querySelector("#pizarra");

    await vi.advanceTimersByTimeAsync(61_000);

    const nuevo = document.querySelector("#pizarra");
    expect(nuevo).not.toBe(viejo);
    // El handler resuelve el banner ACTUAL en cada clic, así que el reemplazo no lo deja huérfano.
    expect(() => document.body.click()).not.toThrow();
  });
});
