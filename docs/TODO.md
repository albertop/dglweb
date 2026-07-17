# TODO — dglweb

Lista de pendientes que van surgiendo sobre la marcha. (Ítems de decisión / afinado, no el
roadmap de fases — eso está en `BUILD_PLAN.md`.)

## Diseño / branding

- [x] ~~Definir el subtítulo del brand~~ → **descartado**: se quita, es redundante con el nombre.
- [ ] Afinar el tamaño del brand en móvil (el nombre completo se recorta un poco a 375px).

## Contenido

- [ ] Escribir los 8–12 artículos semilla (cuello de botella — empezar temprano, en paralelo).

## Deferido a Fase 8 (hardening de prod) — de code review

- [ ] **Imagen prod separada:** Dockerfile de producción con `collectstatic` en el build, solo
  deps de runtime, `config.settings.prod` por defecto, gunicorn, y fallo-ruidoso si faltan
  secretos. (El manifest storage de prod requiere `collectstatic`, que hoy no corre en el build.)
- [ ] **Vendorizar Bootstrap + fuentes** (o al menos SRI): hoy vienen de CDN sin `integrity`.
  Self-host mejora resiliencia (Principio #0), privacidad y prepara CSP.
- [ ] **`restart` policy** del contenedor web en el compose de prod.

## Templates — cuando existan las páginas (Fases 4–5)

- [ ] Nav (Artículos/Líderes/Jugadores/Entrar) y buscador apuntan a `#`/submit desactivado.
  Poner URLs reales o esconderlos hasta que las páginas existan.

## Por decidir (traído del CONCEPT)

- [ ] Proveedor de ad server hosted (GAM vs AdButler/Broadstreet/AdSpeed).
- [ ] Listado exacto de métricas sabermétricas por página de jugador.
- [ ] Redactar legal: privacidad + consentimiento de cookies + ToS.
- [ ] Dónde/ cuándo se activa el muro de registro (post-launch).
