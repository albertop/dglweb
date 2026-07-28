/* El aislamiento del modal de video — FE-01 del review v10.
 *
 * QUÉ SE PROTEGE
 * --------------
 * El modal se anuncia con `role="dialog"` y `aria-modal="true"`, que es una promesa concreta: el
 * resto de la página queda fuera de alcance mientras está abierto. El teclado no la cumplía. Con el
 * video abierto, un par de Tab llevaban el foco a los enlaces de debajo del overlay — invisibles
 * detrás del fondo negro, pero perfectamente enfocables y activables con Enter.
 *
 * No es un fallo que se vea mirando la pantalla, y por eso llevaba ahí desde que existe el modal.
 *
 * POR QUÉ SE PRUEBA EL `inert` Y NO EL RECORRIDO DEL FOCO
 * -------------------------------------------------------
 * Porque jsdom no implementa el comportamiento de `inert`: refleja la propiedad, pero no impide que
 * `focus()` funcione ni simula el orden de tabulación del navegador. Una prueba que pulsara Tab y
 * mirara `document.activeElement` pasaría en verde con el atributo puesto o sin ponerlo, o sea que
 * no probaría nada.
 *
 * Lo que sí se puede comprobar de verdad es la decisión: que el fondo se apaga al abrir, que se
 * enciende al cerrar, y que no se enciende lo que ya estaba apagado por otro motivo. El navegador se
 * encarga del resto — y del resto sí hay una comprobación a mano en `docs/PRUEBAS_DESPLIEGUE.md`.
 */
import { readFileSync } from "node:fs";
import { beforeEach, describe, expect, it, vi } from "vitest";

const FUENTE = readFileSync("static/js/video.js", "utf8");

const PAGINA = `
  <header id="cabecera"><a href="/jugadores/">Jugadores</a></header>
  <main id="cuerpo">
    <button class="dgl-video" data-video="/clip.mp4" data-titulo="Un jonrón">▶</button>
  </main>
  <footer id="pie"><a href="/contacto/">Contacto</a></footer>`;

function abrirElVideo() {
  document.querySelector(".dgl-video").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
}

function cerrarConEscape() {
  document.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
}

function fondo() {
  return [document.getElementById("cabecera"), document.getElementById("cuerpo"), document.getElementById("pie")];
}

describe("el aislamiento del modal de video", () => {
  beforeEach(() => {
    document.body.innerHTML = PAGINA;
    // jsdom no reproduce medios: sin estos tres, abrir y cerrar revientan antes de llegar a lo que
    // se prueba. `pause` y `load` son los que corta `cerrar()` para que el mp4 deje de bajar.
    window.HTMLMediaElement.prototype.play = vi.fn(() => Promise.resolve());
    window.HTMLMediaElement.prototype.pause = vi.fn();
    window.HTMLMediaElement.prototype.load = vi.fn();
    new Function(FUENTE)();
  });

  it("apaga el resto de la página mientras el video está abierto", () => {
    expect(fondo().every((e) => e.inert)).toBe(false);

    abrirElVideo();

    expect(fondo().every((e) => e.inert)).toBe(true);
  });

  it("no se apaga a sí mismo, que si no no habría cómo cerrarlo", () => {
    abrirElVideo();

    const modal = document.querySelector(".dgl-modal");
    expect(modal).not.toBeNull();
    expect(modal.inert).toBeFalsy();
    expect(document.activeElement).toBe(document.querySelector(".dgl-modal-cerrar"));
  });

  it("vuelve a encender la página al cerrar", () => {
    abrirElVideo();
    cerrarConEscape();

    expect(fondo().some((e) => e.inert)).toBe(false);
  });

  it("devuelve el foco al botón que lo abrió, que ya no está inerte", () => {
    const boton = document.querySelector(".dgl-video");

    abrirElVideo();
    cerrarConEscape();

    expect(document.activeElement).toBe(boton);
  });

  it("no enciende lo que ya estaba apagado antes de abrir", () => {
    // El caso que obliga a llevar la lista en vez de recorrer los hijos otra vez al cerrar: si algún
    // día otra cosa apaga una zona de la página, cerrar un video no puede resucitarla.
    const pie = document.getElementById("pie");
    pie.inert = true;

    abrirElVideo();
    cerrarConEscape();

    expect(pie.inert).toBe(true);
  });

  it("abrir dos veces seguidas no deja la página apagada", () => {
    abrirElVideo();
    cerrarConEscape();
    abrirElVideo();
    cerrarConEscape();

    expect(fondo().some((e) => e.inert)).toBe(false);
  });
});
