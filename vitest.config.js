/* El corredor del JavaScript del sitio.
 *
 * POR QUÉ EXISTE, Y POR QUÉ NO EXISTÍA ANTES
 * ------------------------------------------
 * El gate de este proyecto es Python puro —`ruff`, `mypy`, `pytest`— y meter Node cuesta. Cuando el
 * review v6 levantó FE-02 (el teclado del buscador sin pruebas) se aplazó con un argumento explícito:
 * «vale la pena cuando exista una segunda pieza de JS; con una sola, el corredor cuesta más que lo
 * que protege».
 *
 * Esa condición se cumplió. Hoy son OCHO archivos y ~860 líneas, y varias se escribieron el 27-07 al
 * sacar el JavaScript en línea por la CSP — o sea que ese trabajo movió comportamiento desde las
 * plantillas hasta archivos que ninguna prueba tocaba.
 *
 * `jsdom` y no un navegador de verdad: lo que hay que probar son decisiones de teclado y de DOM, no
 * pintado. Un navegador headless en el CI descargaría cientos de megas por corrida para responder las
 * mismas preguntas.
 */
export default {
  test: {
    environment: "jsdom",
    include: ["tests/js/**/*.test.js"],
    // Sin `node_modules` ni el árbol de Python, que si no `vitest` se pone a mirar 200 MB de venv.
    exclude: ["node_modules/**", ".venv/**", "staticfiles/**"],
  },
};
