/* Los botones de compartir — QA-02 del review v13.
 *
 * QUÉ SE PROTEGE, Y NO ES EL CAMINO FELIZ
 * ----------------------------------------
 * Los cinco botones son `<a href>` planos que funcionan sin JavaScript. Este archivo solo añade dos
 * cosas encima: el menú nativo del sistema donde existe, y que «Copiar enlace» copie de verdad.
 *
 * Lo que puede salir mal está todo en los bordes:
 *
 *   - `navigator.share` NO EXISTE en la mayoría del escritorio. Enseñar ese botón donde no hace nada
 *     deja un botón muerto en la mitad de las visitas.
 *   - Cerrar el menú del sistema sin elegir nada RECHAZA la promesa con `AbortError`. Sin `catch`, eso
 *     sale como error en la consola cada vez que alguien se arrepiente — que es lo más normal del
 *     mundo.
 *   - `navigator.clipboard` solo existe en contexto seguro. En el localhost por http hay que caer al
 *     respaldo, o el botón parece roto justo donde se prueba.
 *
 * Ninguno se ve en un navegador de escritorio moderno con https, que es donde uno mira.
 */
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const FUENTE = readFileSync("static/js/compartir.js", "utf8");

const URL_ARTICULO = "https://dominicanosengrandesligas.com/articulos/soto/";
const TITULO = "Soto la sacó tres veces";

/* El marcado de `widgets/_compartir.html`, recortado a lo que este script toca. El icono en SVG va
 * dentro del botón a propósito: es parte de lo que se prueba. */
const CAJA = `
  <div class="dgl-compartir" role="group" data-compartir
       data-titulo="${TITULO}" data-url="${URL_ARTICULO}">
    <button type="button" class="dgl-compartir-boton d-none" data-compartir-nativo hidden>
      <svg class="dgl-compartir-icono" viewBox="0 0 24 24" aria-hidden="true"><path d="M18 16"/></svg>
      <span>Compartir…</span>
    </button>
    <a class="dgl-compartir-boton" data-red="whatsapp" href="https://wa.me/?text=x">
      <svg class="dgl-compartir-icono" viewBox="0 0 24 24" aria-hidden="true"><path d="M17 14"/></svg>
      <span>WhatsApp</span>
    </a>
    <a class="dgl-compartir-boton" data-copiar href="${URL_ARTICULO}">
      <svg class="dgl-compartir-icono" viewBox="0 0 24 24" aria-hidden="true"><path d="M3.9 12"/></svg>
      <span>Copiar enlace</span>
    </a>
  </div>`;

function correr() {
  new Function(FUENTE)();
}

const nativo = () => document.querySelector("[data-compartir-nativo]");
const copiar = () => document.querySelector("[data-copiar]");

function clic(elemento) {
  const evento = new window.MouseEvent("click", { bubbles: true, cancelable: true });
  elemento.dispatchEvent(evento);
  return evento;
}

/** Deja que se resuelvan las promesas pendientes sin adelantar los temporizadores. */
const asentar = () => new Promise((r) => setTimeout(r, 0));

describe("el botón del menú nativo", () => {
  it("sigue oculto donde el navegador no lo soporta", () => {
    /* El escritorio, o sea la mitad de las visitas. Un botón visible que no hace nada es peor que no
     * tenerlo. */
    correr();

    expect(nativo().hidden).toBe(true);
    expect(nativo().classList.contains("d-none")).toBe(true);
  });

  it("aparece donde sí, y hay que quitarle las DOS formas de ocultarlo", () => {
    /* `hidden` y `d-none` a la vez porque la clase de Bootstrap lleva `!important` y ganaría al
     * atributo. Quitar solo una deja el botón invisible en un teléfono — justo donde sirve. */
    navigator.share = vi.fn(() => Promise.resolve());

    correr();

    expect(nativo().hidden).toBe(false);
    expect(nativo().classList.contains("d-none")).toBe(false);
  });

  it("comparte el título y la URL del artículo, no los de la página", () => {
    navigator.share = vi.fn(() => Promise.resolve());
    correr();

    clic(nativo());

    expect(navigator.share).toHaveBeenCalledWith({ title: TITULO, text: TITULO, url: URL_ARTICULO });
  });

  it("cerrar el menú sin elegir nada no ensucia la consola", async () => {
    /* EL CASO MÁS FRECUENTE DE TODOS: se abre el menú del sistema y se cierra. `navigator.share`
     * rechaza con `AbortError`, y sin `catch` eso es un rechazo sin atrapar en cada visita. */
    const sinAtrapar = vi.fn();
    process.on("unhandledRejection", sinAtrapar);
    navigator.share = vi.fn(() => Promise.reject(new Error("AbortError")));
    correr();

    clic(nativo());
    await asentar();

    process.off("unhandledRejection", sinAtrapar);
    expect(sinAtrapar).not.toHaveBeenCalled();
  });
});

describe("copiar el enlace", () => {
  it("no navega al propio artículo", () => {
    /* El botón es un `<a href>` para que sin JavaScript no quede muerto. Con JavaScript, dejar que el
     * clic siga su curso recargaría la misma página y el enlace nunca llegaría al portapapeles. */
    correr();

    const evento = clic(copiar());

    expect(evento.defaultPrevented).toBe(true);
  });

  it("copia la URL de compartir", async () => {
    const escribir = vi.fn(() => Promise.resolve());
    navigator.clipboard = { writeText: escribir };
    window.isSecureContext = true;
    correr();

    clic(copiar());
    await asentar();

    expect(escribir).toHaveBeenCalledWith(URL_ARTICULO);
  });

  it("cae al respaldo cuando el contexto no es seguro", async () => {
    /* El localhost por http, que es donde se prueba todo. Sin respaldo, el botón no haría nada
     * exactamente en el sitio donde uno lo comprueba antes de desplegar. */
    navigator.clipboard = { writeText: vi.fn(() => Promise.resolve()) };
    window.isSecureContext = false;
    document.execCommand = vi.fn(() => true);
    correr();

    clic(copiar());
    await asentar();

    expect(navigator.clipboard.writeText).not.toHaveBeenCalled();
    expect(document.execCommand).toHaveBeenCalledWith("copy");
  });

  it("el respaldo mete la caja EN el documento, porque si no no se puede seleccionar", async () => {
    /* Un elemento con `display:none` no se puede seleccionar y `execCommand` no copiaría nada. Va
     * fuera de la vista con `position:fixed`, que es distinto. Y se quita después. */
    window.isSecureContext = false;
    let habia = null;
    document.execCommand = vi.fn(() => {
      const caja = document.querySelector("textarea");
      habia = caja && caja.isConnected && caja.style.display !== "none";
      return true;
    });
    correr();

    clic(copiar());
    await asentar();

    expect(habia).toBe(true);
    expect(document.querySelector("textarea")).toBe(null);
  });
});

describe("lo que se le dice a la persona", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("avisa que copió, y devuelve el texto original después", async () => {
    navigator.clipboard = { writeText: () => Promise.resolve() };
    window.isSecureContext = true;
    correr();

    clic(copiar());
    await vi.advanceTimersByTimeAsync(0);
    const durante = copiar().textContent.trim();
    await vi.advanceTimersByTimeAsync(2000);

    expect(durante).toBe("¡Copiado!");
    expect(copiar().textContent.trim()).toBe("Copiar enlace");
  });

  it("dice que no pudo en vez de quedarse callado", async () => {
    /* Un botón que no hace nada y no avisa es peor que uno que reconoce que no pudo: en el primer caso
     * la persona cree que copió y pega otra cosa. */
    navigator.clipboard = { writeText: () => Promise.reject(new Error("denegado")) };
    window.isSecureContext = true;
    correr();

    clic(copiar());
    await vi.advanceTimersByTimeAsync(0);

    expect(copiar().textContent.trim()).toBe("No se pudo copiar");
  });

  it("el icono sigue ahí después de copiar", async () => {
    /* LA TRAMPA DE `textContent`: asignarlo BORRA todos los hijos, y el icono en SVG es uno de ellos.
     * El botón quedaría de texto pelado para siempre —el aviso se deshace, el icono no— y desalineado
     * respecto a los otros cuatro. No revienta nada, así que solo se ve mirando. */
    navigator.clipboard = { writeText: () => Promise.resolve() };
    window.isSecureContext = true;
    correr();

    clic(copiar());
    await vi.advanceTimersByTimeAsync(2000);

    expect(copiar().querySelector("svg")).not.toBe(null);
  });

  it("dos clics seguidos no dejan «¡Copiado!» pegado para siempre", async () => {
    /* Si el segundo clic guardara como «original» el texto que puso el primero, el botón se quedaría
     * diciendo «¡Copiado!» el resto de la visita. */
    navigator.clipboard = { writeText: () => Promise.resolve() };
    window.isSecureContext = true;
    correr();

    clic(copiar());
    await vi.advanceTimersByTimeAsync(100);
    clic(copiar());
    await vi.advanceTimersByTimeAsync(2000);

    expect(copiar().textContent.trim()).toBe("Copiar enlace");
  });
});

describe("varias cajas en la misma página", () => {
  it("monta las dos, la de arriba del artículo y la del final", async () => {
    document.body.innerHTML = CAJA + CAJA;
    navigator.share = vi.fn(() => Promise.resolve());

    correr();

    expect([...document.querySelectorAll("[data-compartir-nativo]")].every((b) => !b.hidden)).toBe(true);
  });
});

beforeEach(() => {
  document.body.innerHTML = CAJA;
  // `share` y `clipboard` no existen en jsdom: se ponen y se quitan por prueba para que cada una
  // declare el navegador que está simulando.
  delete navigator.share;
  delete navigator.clipboard;
  window.isSecureContext = false;
});
