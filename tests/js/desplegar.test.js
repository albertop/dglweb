/* El «ver más» delegado de `site.js` — FE-01 del review v19.
 *
 * QUÉ SE PROTEGE
 * --------------
 * Este mecanismo lo usan cuatro controles del sitio y no tenía una sola prueba. El que lo destapó
 * fue el «Ver más artículos» de la portada en móvil: se escribió como un `<button>` sin `href`, así
 * que si `site.js` no llegaba a ejecutarse —por CSP, por un error anterior en el archivo, o sin
 * JavaScript— el lector veía un control y al pulsarlo no pasaba nada.
 *
 * El arreglo es mejora progresiva: es un enlace de verdad al índice, y este JS lo asciende a
 * desplegable cortándole la navegación. Las dos rutas tienen que seguir funcionando, y eso es lo que
 * fijan estas pruebas — sobre todo la del `preventDefault`, que es la única línea que separa
 * «despliega» de «se va a otra página».
 */
import { readFileSync } from "node:fs";
import { beforeAll, beforeEach, describe, expect, it } from "vitest";

const FUENTE = readFileSync("static/js/site.js", "utf8");

const PORTADA = `
  <div class="row" id="portada-articulos">
    <div class="col">visible</div>
    <div class="col dgl-art-de-mas">escondido</div>
  </div>
  <a id="control" href="/articulos/" data-desplegar="#portada-articulos"
     aria-controls="portada-articulos" aria-expanded="false">Ver más artículos</a>`;

describe("el desplegable delegado", () => {
  let control;
  let caja;

  // El script se evalúa UNA vez, como en producción: registra un listener delegado en `document` y
  // ese documento sobrevive a todas las pruebas del archivo. Evaluándolo en cada `beforeEach` se
  // acumulaban listeners y un solo clic alternaba la clase tantas veces como pruebas hubieran
  // corrido antes — la cuarta acababa cerrada y el fallo parecía del producto.
  beforeAll(() => {
    new Function(FUENTE)();
  });

  beforeEach(() => {
    document.body.innerHTML = PORTADA;
    control = document.getElementById("control");
    caja = document.getElementById("portada-articulos");
  });

  it("despliega la caja que dice su `data-desplegar`", () => {
    control.click();

    expect(caja.classList.contains("esta-desplegado")).toBe(true);
  });

  it("NO navega cuando el JS está vivo", () => {
    // El caso que motivó el cambio. Sin `preventDefault`, el enlace se lleva al lector al índice y el
    // despliegue no se llega a ver — la mejora progresiva quedaría al revés.
    const evento = new MouseEvent("click", { bubbles: true, cancelable: true });

    control.dispatchEvent(evento);

    expect(evento.defaultPrevented).toBe(true);
  });

  it("sí deja navegar si la caja no está en la página", () => {
    // Sin destino, más vale que el enlace se comporte como enlace. Es la red de abajo para una
    // plantilla que cambie el id y se olvide del atributo.
    control.dataset.desplegar = "#no-existe";
    const evento = new MouseEvent("click", { bubbles: true, cancelable: true });

    control.dispatchEvent(evento);

    expect(evento.defaultPrevented).toBe(false);
  });

  it("anuncia el estado y lo devuelve al cerrarse", () => {
    control.click();
    expect(control.getAttribute("aria-expanded")).toBe("true");

    control.click();
    expect(control.getAttribute("aria-expanded")).toBe("false");
    expect(caja.classList.contains("esta-desplegado")).toBe(false);
  });

  it("cambia el texto y lo restaura, para no mentir con la lista abierta", () => {
    control.click();
    expect(control.textContent).toBe("Ver menos");

    control.click();
    expect(control.textContent).toBe("Ver más artículos");
  });
});
