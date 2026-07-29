# El servidor de anuncios — Revive, autoalojado

**Estado: en montaje. Decidido el 2026-07-28.**

Este documento es el plan y, sobre todo, **por qué** cada pieza está donde está. Los pasos se van
marcando aquí a medida que se completan.

---

## La decisión

**Adcio vende la publicidad directamente a sus clientes.** Eso es lo primero que hay que entender,
porque descarta media industria: no hace falta una red que llene el inventario automáticamente, hace
falta un servidor que publique lo que ya se vendió — que rote creatividades, respete fechas, cuente
impresiones y saque el informe con el que se factura.

**Se elige Revive Adserver.** No por ganar una comparación, sino porque casi no hay con quién
compararlo:

| Opción | Por qué no |
|---|---|
| **OpenX Source** | Dejó de existir. La empresa se fue a lo programático y el código libre se bifurcó… en Revive. O sea que Revive **es** el heredero. |
| **Broadstreet, AdButler, AdSpeed, Kevel, Epom, Adnuntius** | Comerciales y alojados por el proveedor. Ni libres ni autoalojables. |
| **Prebid Server** | Libre y serio, pero resuelve **otro problema**: subastas programáticas. No sirve para «rotarle el banner a tres clientes». |
| **Google Ad Manager** | Gratis y hace exactamente esto, pero mete a Google en cada página con sus cookies. Descartado por lo mismo que se descartó Google Analytics. |
| **Construirlo dentro del sitio** | **Descartado por el dueño (2026-07-28), sin discusión.** No se le dedica tiempo a construir un servidor de anuncios. |

Lo que queda por debajo son proyectos de una persona, sin publicaciones en años, o cosas de nicho.
Nada a lo que se le confíe el JavaScript que ve cada visitante.

**Comprobado antes de decidir (2026-07-28):** Revive está vivo — versión **v6.0.8**, último commit el
**9 de julio de 2026**, repositorio sin archivar, licencia libre.

### Lo que cuesta, aceptado a sabiendas

Dos cosas, y ninguna es menor:

1. **MariaDB en el VPS.** Revive no habla Postgres. Es un segundo motor de base de datos que
   respaldar, actualizar y vigilar, y **rompe la regla explícita del dueño de tener una sola
   instancia**. Se acepta porque no hay alternativa: ningún servidor de anuncios libre usa Postgres.
2. **PHP público que hay que mantener parcheado.** Es la pieza **más expuesta** de todo el
   despliegue: sirve código a cada visitante en cada página. Viene del linaje de OpenX y arrastra
   historial de avisos de seguridad. No es «instalar y olvidar».

---

## La arquitectura

```
navegador ──► nginx (VPS)
                │
                ├── ads.dominicanosengrandesligas.com/<entrega>/   PÚBLICO
                │        └──► revive (php-fpm) ──► mariadb
                │
                └── ads.dominicanosengrandesligas.com/<panel>/     LISTA BLANCA DE IP
                         └──► revive (php-fpm)
```

Los dos contenedores atados a `127.0.0.1`, como todo lo demás del VPS: quien entra, entra por nginx.

### Decisión 1 — subdominio del sitio, no de `prdm0.com`

`ads.dominicanosengrandesligas.com` y no un dominio aparte, **y no es cosmético**: es lo que hace
que los anuncios sean *first-party*. Servidos desde otro dominio serían terceros para el navegador —
justo lo que cortan los bloqueadores, y lo que obligaría a abrir la CSP de par en par y a reescribir
la página de privacidad.

### Decisión 2 — el subdominio se llama `ads`, y el nombre casi da igual

**Esto empezó siendo un aviso equivocado y quedó corregido con datos.** La recomendación inicial fue
evitar `ads`, `adserver`, `banner` y `doubleclick` porque «están en las listas de bloqueo por sí
solas». **Se comprobó y es falso.**

Medido el 2026-07-28 contra EasyList (84.414 reglas) y EasyPrivacy (56.397): las 21 reglas que
empiezan por `||ads.` apuntan **todas a empresas concretas** —`ads.linkedin.com`, `ads.samsung.com`,
`ads.sportradar.com`— y **no existe ninguna regla genérica** que case con un `ads.` cualquiera. Un
subdominio nuevo no coincide con ninguna.

Lo que **sí** es genérico son las rutas, y de eso se ocupa la decisión 5. El riesgo estaba en otro
sitio del que se creía.

### Decisión 3 — nginx partido en dos, y esto es lo que más importa acertar

Revive tiene **dos mitades con necesidades opuestas**:

- **La entrega** (`/www/delivery/…`) la pide el navegador de cada visitante. Tiene que ser
  **pública**.
- **El panel** lo usan el dueño y Adcio. Va con la **misma lista blanca de IP que pgAdmin**.

Si se protege todo, no se ven los anuncios. Si se abre todo, el panel de administración de un PHP con
historial de vulnerabilidades queda expuesto en internet. **Las dos mitades se separan por ruta.**

### Decisión 4 — imagen propia, no una de la comunidad

**No existe imagen oficial de Revive**, y el repositorio no trae `Dockerfile`. Buscadas en Docker Hub
el 2026-07-28: diez resultados, **la más popular con 5 estrellas** y ninguna mantenida.

Se construye la imagen desde el paquete oficial de Revive sobre una imagen oficial de PHP. Es más
trabajo, y es la única forma defendible para la pieza que sirve código a cada visitante. Es además el
mismo camino que ya sigue el sitio con `Dockerfile.prod`.

### Decisión 5 — renombrar las rutas de entrega. ESTO ES LO QUE DE VERDAD IMPORTA

Las rutas por defecto de Revive están en las listas **por su ruta, sin mirar el dominio**. Extraídas
de EasyList el 2026-07-28, tal cual:

```
/www/delivery/*     $script,subdocument
/ajs.php?           $script
/afr.php?           $~xmlhttprequest
/adserver.
/delivery/ag.php  /delivery/apu.php  /delivery/avw.php  /delivery/fc.php  /delivery/lg.php
```

O sea que **da igual el subdominio y da igual que sea first-party**: con la instalación de fábrica,
cualquier visitante con un bloqueador no ve el anuncio. Y **a los clientes se les factura por
impresiones**, así que cada una bloqueada es dinero que no se cobra.

Se renombran durante la instalación. Es el único punto de este documento que no admite atajo.

---

## Los pasos

- [x] **1. Subdominio y DNS.** **HECHO (2026-07-28)**: `ads.dominicanosengrandesligas.com` → A → IP del VPS.
- [ ] **2. La imagen.** `Dockerfile` propio: PHP oficial + el paquete de Revive, con las extensiones
      que pide (`mysqli`, `gd`, `zip`, `openssl`).
- [ ] **3. El stack en Portainer.** Revive + MariaDB, atados a `127.0.0.1`, con volumen para la base y
      para las creatividades que suba el editor. Las variables por el patrón de siempre: declaradas en
      `environment:` **y** con valor en las «Environment variables» del stack.
- [ ] **4. nginx.** Certificado TLS para el subdominio y el `server` partido en dos por ruta.
- [ ] **5. Instalación.** El asistente de Revive, el renombrado de rutas y la cuenta de administrador.
- [ ] **6. Enganchar el sitio.** El dominio en `dglweb/core/csp.py` y la etiqueta en las zonas de
      anuncio, que ya están maquetadas con alto fijo.

---

## Lo que hay que recordar cuando esté funcionando

**La CSP lo va a bloquear en silencio.** El sitio manda `script-src 'self'` desde el 2026-07-27, así
que hasta que `ads.dominicanosengrandesligas.com` esté en esa lista, la etiqueta no carga: el hueco
se queda vacío y el único sitio donde se explica es la consola del navegador. Ver `core/csp.py`.

**Las páginas legales cambian.** Hoy la política de cookies dice que quien solo navega no recibe
ninguna, y hay una prueba que lo sostiene (`tests/test_legal.py`). Revive puede servir sin cookies,
pero **el límite de frecuencia las necesita**: si se usa esa función, hay que reescribir la página y
montar el cartel de consentimiento. Decidirlo a conciencia, no descubrirlo.

**La prueba de terceros se va a caer, y a propósito.**
`test_el_sitio_publico_no_pide_nada_a_terceros` exige que el único externo sea el declarado en
`settings.ANALITICA_URL`. Al añadir el servidor de anuncios hay que ampliarla **nombrando el nuevo
origen**, no relajándola: el día que entre un cuarto script, alguien tiene que enterarse.

**El respaldo tiene que incluir MariaDB.** `deploy/respaldo.sh` guarda hoy Postgres y `media/`. Un
servidor de anuncios sin sus campañas es un servidor vacío, y las creatividades que suba Adcio solo
existen ahí.

**Y hay que mantenerlo al día.** Es la pieza más expuesta del VPS. Conviene vigilar las publicaciones
de Revive y no dejar pasar las de seguridad.
