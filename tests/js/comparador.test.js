/* El generador de comparaciones: qué campos se ven y qué años se ofrecen.
 *
 * QUÉ SE PROTEGE. Este archivo no calcula nada —el servidor revalida todo— así que lo único que
 * puede romper es dejar al formulario diciendo una cosa y enviando otra. Los tres modos de hacerlo:
 *
 *   un campo escondido que se sigue enviando   → el servidor lee un año que nadie pidió.
 *   un desplegable habilitado y vacío          → se puede enviar sin temporada y sin darse cuenta.
 *   los años del pelotero anterior             → se compara a quien no era.
 *
 * Ninguno se ve mirando la pantalla: el formulario parece correcto en los tres casos.
 *
 * El script se lee del disco y se evalúa DESPUÉS de armar el DOM de cada prueba, como en
 * `buscador.test.js`: se ejecuta solo al cargarse y un `import` se cachearía entre pruebas.
 */
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const FUENTE = readFileSync("static/js/comparador.js", "utf8");

const ANIOS_UNO = [2024, 2023, 2021, 2019, 2018];
const ANIOS_OTRO = [2009, 2008, 2006];

/** El formulario, con la modalidad pedida marcada. */
function montar(modo = "mejores") {
  document.body.innerHTML = `
    <form id="cmp-form">
      <input type="hidden" id="uno" name="uno" value="">
      <input type="hidden" id="otro" name="otro" value="">
      <div class="dgl-cmp-anio" data-visible-si="modo-temporadas">
        <select id="anio_uno" name="anio_uno" data-anios="/comparar/temporadas/" data-elegido="uno" disabled></select>
      </div>
      <div class="dgl-cmp-anio" data-visible-si="modo-temporadas">
        <select id="anio_otro" name="anio_otro" data-anios="/comparar/temporadas/" data-elegido="otro" disabled></select>
      </div>
      <input type="radio" name="modo" id="modo-mejores" value="mejores" ${modo === "mejores" ? "checked" : ""}>
      <input type="radio" name="modo" id="modo-carrera" value="carrera" ${modo === "carrera" ? "checked" : ""}>
      <input type="radio" name="modo" id="modo-temporadas" value="temporadas" ${modo === "temporadas" ? "checked" : ""}>
      <div class="dgl-cmp-sub" data-visible-si="modo-mejores">
        <select id="cuantas" name="cuantas"><option value="5">5 temporadas</option></select>
      </div>
    </form>`;
}

/** Responde con los años que le tocan a cada slug. */
function servidor(mapa) {
  global.fetch = vi.fn(function (url) {
    const slug = decodeURIComponent(url.split("jugador=")[1] || "");
    return Promise.resolve({ json: () => Promise.resolve({ anios: mapa[slug] || [] }) });
  });
}

/** Elige un pelotero como lo hace `buscador.js`: escribe el slug y avisa con `change`. */
async function elegir(id, slug) {
  const oculto = document.getElementById(id);
  oculto.value = slug;
  oculto.dispatchEvent(new Event("change", { bubbles: true }));
  // El `fetch` se resuelve en microtareas encadenadas; un tick del bucle de eventos las suelta todas.
  await new Promise(function (listo) {
    setTimeout(listo, 0);
  });
}

function marcar(id) {
  const radio = document.getElementById(id);
  radio.checked = true;
  radio.dispatchEvent(new Event("change", { bubbles: true }));
}

beforeEach(() => {
  servidor({ "juan-soto-665742": ANIOS_UNO, "albert-pujols-405395": ANIOS_OTRO });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("los campos que dependen de la modalidad", () => {
  it("esconde y DESHABILITA lo que no toca", () => {
    montar("mejores");
    new Function(FUENTE)();

    const anio = document.getElementById("anio_uno");
    expect(anio.closest("[data-visible-si]").classList.contains("d-none")).toBe(true);
    expect(anio.disabled).toBe(true, "escondido pero enviándose sería peor que visible");
    expect(document.getElementById("cuantas").disabled).toBe(false);
  });

  it("cambia de bloque al cambiar de modalidad", () => {
    montar("mejores");
    new Function(FUENTE)();

    marcar("modo-temporadas");

    expect(document.getElementById("anio_uno").closest("[data-visible-si]").classList.contains("d-none")).toBe(false);
    expect(document.getElementById("cuantas").disabled).toBe(true);
  });

  it("con la carrera completa no pide nada más", () => {
    montar("carrera");
    new Function(FUENTE)();

    expect(document.getElementById("cuantas").disabled).toBe(true);
    expect(document.getElementById("anio_uno").disabled).toBe(true);
  });
});

describe("el desplegable de temporadas", () => {
  it("nace vacío y apagado: no hay años hasta que hay pelotero", () => {
    montar("temporadas");
    new Function(FUENTE)();

    const anio = document.getElementById("anio_uno");
    expect(anio.options.length).toBe(0);
    expect(anio.disabled).toBe(true, "un desplegable vacío y habilitado se puede enviar sin elegir");
  });

  it("se llena con los años del pelotero elegido", async () => {
    montar("temporadas");
    new Function(FUENTE)();

    await elegir("uno", "juan-soto-665742");

    const anio = document.getElementById("anio_uno");
    expect(Array.from(anio.options).map((o) => Number(o.value))).toEqual(ANIOS_UNO);
    expect(anio.disabled).toBe(false);
  });

  it("cada lado recibe los suyos", async () => {
    montar("temporadas");
    new Function(FUENTE)();

    await elegir("uno", "juan-soto-665742");
    await elegir("otro", "albert-pujols-405395");

    expect(Array.from(document.getElementById("anio_uno").options).map((o) => Number(o.value))).toEqual(ANIOS_UNO);
    expect(Array.from(document.getElementById("anio_otro").options).map((o) => Number(o.value))).toEqual(ANIOS_OTRO);
  });

  it("cambiar de pelotero reemplaza los años, no los acumula", async () => {
    montar("temporadas");
    new Function(FUENTE)();

    await elegir("uno", "juan-soto-665742");
    await elegir("uno", "albert-pujols-405395");

    expect(Array.from(document.getElementById("anio_uno").options).map((o) => Number(o.value))).toEqual(ANIOS_OTRO);
  });

  it("se vacía y se apaga si se deshace la elección", async () => {
    montar("temporadas");
    new Function(FUENTE)();
    await elegir("uno", "juan-soto-665742");

    await elegir("uno", "");

    const anio = document.getElementById("anio_uno");
    expect(anio.options.length).toBe(0);
    expect(anio.disabled).toBe(true);
  });

  it("se queda apagado si la modalidad no es la de temporada", async () => {
    montar("mejores");
    new Function(FUENTE)();

    await elegir("uno", "juan-soto-665742");

    const anio = document.getElementById("anio_uno");
    expect(anio.options.length).toBe(5, "los años se cargan igual, para no repetir la petición");
    expect(anio.disabled).toBe(true, "pero no se envían: la modalidad no los pidió");
  });

  it("un pelotero sin temporadas comparables deja el desplegable apagado", async () => {
    montar("temporadas");
    new Function(FUENTE)();

    await elegir("uno", "un-cafe-cualquiera-1");

    expect(document.getElementById("anio_uno").disabled).toBe(true);
  });

  it("si el servidor falla no rompe el formulario", async () => {
    montar("temporadas");
    global.fetch = vi.fn(() => Promise.reject(new Error("sin red")));
    new Function(FUENTE)();

    await elegir("uno", "juan-soto-665742");

    expect(document.getElementById("anio_uno").disabled).toBe(true);
  });

  it("al volver del servidor con un pelotero puesto, carga sus años solo", async () => {
    montar("temporadas");
    document.getElementById("uno").value = "juan-soto-665742";

    new Function(FUENTE)();
    await vi.waitFor(() => expect(document.getElementById("anio_uno").options.length).toBe(5));

    expect(document.getElementById("anio_uno").disabled).toBe(false);
  });
});

describe("volver al paso de temporadas", () => {
  /* EL AÑO ELEGIDO NO SE PUEDE PERDER — finding FE-01 del review v24.
   *
   * Al volver del resumen, el `<select>` llega VACÍO: el servidor no puede saber los años sin
   * consultarlos, así que manda el elegido aparte en `data-elegido-valor` y el JS los rellena después.
   * Leyendo solo `select.value` —que en ese momento es «»— el desplegable se quedaba con el primer año
   * de la lista. Pulsar «Siguiente» sin mirar generaba OTRA comparación, y nada en pantalla lo decía.
   */
  it("restaura el año que ya estaba elegido", async () => {
    document.body.innerHTML = `
      <form id="cmp-form">
        <input type="hidden" id="uno" name="uno" value="juan-soto-665742">
        <div class="dgl-cmp-anio" data-visible-si="modo-temporadas">
          <select id="anio_uno" name="anio_uno" data-anios="/comparar/temporadas/"
                  data-elegido="uno" data-elegido-valor="2021" disabled></select>
        </div>
        <input type="radio" name="modo" id="modo-temporadas" value="temporadas" checked>
      </form>`;
    servidor({ "juan-soto-665742": ANIOS_UNO });

    new Function(FUENTE)();
    await vi.waitFor(() => expect(document.getElementById("anio_uno").options.length).toBe(5));

    expect(document.getElementById("anio_uno").value).toBe("2021");
  });

  it("sin año previo se queda en el primero, que es lo más reciente", async () => {
    document.body.innerHTML = `
      <form id="cmp-form">
        <input type="hidden" id="uno" name="uno" value="juan-soto-665742">
        <div class="dgl-cmp-anio" data-visible-si="modo-temporadas">
          <select id="anio_uno" name="anio_uno" data-anios="/comparar/temporadas/"
                  data-elegido="uno" data-elegido-valor="" disabled></select>
        </div>
        <input type="radio" name="modo" id="modo-temporadas" value="temporadas" checked>
      </form>`;
    servidor({ "juan-soto-665742": ANIOS_UNO });

    new Function(FUENTE)();
    await vi.waitFor(() => expect(document.getElementById("anio_uno").options.length).toBe(5));

    expect(document.getElementById("anio_uno").value).toBe(String(ANIOS_UNO[0]));
  });
  /* Y SOLO UNA VEZ — finding DEV-01 del review v25. `data-elegido-valor` es estado restaurado del
   * servidor, no una preferencia del `<select>`. Si se queda pegado, cambiar de pelotero en esa misma
   * pantalla hereda el año del anterior: el cálculo sale correcto para lo que se envía, pero no es lo
   * que el usuario pidió. */
  it("no hereda el año al cambiar de pelotero", async () => {
    document.body.innerHTML = `
      <form id="cmp-form">
        <input type="hidden" id="uno" name="uno" value="juan-soto-665742">
        <div class="dgl-cmp-anio" data-visible-si="modo-temporadas">
          <select id="anio_uno" name="anio_uno" data-anios="/comparar/temporadas/"
                  data-elegido="uno" data-elegido-valor="2021" disabled></select>
        </div>
        <input type="radio" name="modo" id="modo-temporadas" value="temporadas" checked>
      </form>`;
    servidor({ "juan-soto-665742": ANIOS_UNO, "otro-pelotero-1": [2022, 2021, 2020] });

    new Function(FUENTE)();
    await vi.waitFor(() => expect(document.getElementById("anio_uno").value).toBe("2021"));

    await elegir("uno", "otro-pelotero-1");

    expect(document.getElementById("anio_uno").value).toBe("2022");
  });
});
