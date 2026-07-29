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

1. ~~**MariaDB en el VPS.**~~ **DESCARTADO: Revive habla PostgreSQL.** La primera versión de este
   documento decía que no, y era falso. Comprobado en su repositorio el 2026-07-28: **`pgsql` es un
   eje de primera clase de su matriz de pruebas** —junto a `mysqli`, con su propio tipo de tablas y
   probado contra PHP 8.1, 8.2, 8.3, 8.4 y 8.5— y `lib/OA/DB.php` tiene 17 referencias a pgsql.

   O sea que **usa el Postgres que ya está**, con su propia base y su propio rol. Se cae el coste más
   grande del plan y **la regla de un solo motor de base de datos sobrevive**.

   La letra pequeña, dicha por honestidad: MySQL es el camino más transitado de Revive y Postgres el
   menos. Pero «lo prueban en CI en cada versión de PHP» es una garantía muy distinta de «dicen que
   se puede».

2. **PHP público que hay que mantener parcheado.** Es la pieza **más expuesta** de todo el
   despliegue: sirve código a cada visitante en cada página. Viene del linaje de OpenX y arrastra
   historial de avisos de seguridad. No es «instalar y olvidar». **Este coste se queda.**

---

## La arquitectura

```
navegador ──► nginx (VPS)
                │
                ├── promo.dominicanosengrandesligas.com/<entrega>/   PÚBLICO
                │        └──► revive (php) ──► el Postgres que YA EXISTE
                │                          (base y rol propios)
                │
                └── promo.dominicanosengrandesligas.com/<panel>/     LISTA BLANCA DE IP
                         └──► revive (php)
```

El contenedor atado a `127.0.0.1`, como todo lo demás del VPS: quien entra, entra por nginx.

### Decisión 1 — subdominio del sitio, no de `prdm0.com`

`promo.dominicanosengrandesligas.com` y no un dominio aparte, **y no es cosmético**: es lo que hace
que los anuncios sean *first-party*. Servidos desde otro dominio serían terceros para el navegador —
justo lo que cortan los bloqueadores, y lo que obligaría a abrir la CSP de par en par y a reescribir
la página de privacidad.

### Decisión 2 — el subdominio se llama `promo`, y el nombre casi da igual

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

- [x] **1. Subdominio y DNS.** **HECHO (2026-07-28)**: `promo.dominicanosengrandesligas.com` → A →
      `107.175.69.53`. Comprobado que resuelve desde fuera.
- [x] **2. La imagen.** **HECHA (2026-07-28)**: `deploy/adserver/Dockerfile`, construida y probada.
      PHP **8.3** —la que fija su propio CI— con `intl`, `pgsql`, `pdo_pgsql` y `zip`; el resto de lo
      que declaran ya viene en la imagen oficial. Se compila desde la etiqueta `v6.0.8` con Composer,
      porque el paquete no se puede automatizar: sus publicaciones de GitHub no traen adjuntos y la
      descarga directa de su web responde 403.

      Comprobado sobre el contenedor levantado: las cuatro extensiones cargan, el panel redirige al
      instalador, `adjs.php` responde 200, y `var/`, `lib/`, `etc/` y `composer.json` dan 403.

      **Dos trampas que solo aparecieron al probarla**, y que están escritas en el propio archivo:

      1. Purgar los `-dev` con `--auto-remove` **se lleva también las bibliotecas de ejecución**
         (`libicuio`, `libpq`, `libzip`) y deja las extensiones sin cargar. Y **la construcción no
         falla**: la imagen sale perfecta y el fallo aparece al arrancar, en unos avisos de PHP que
         nadie mira, con `pgsql` ausente — o sea Revive sin base de datos. Se resuelve con la receta
         de `ldd` que usan las imágenes oficiales de WordPress y Drupal, y ahora hay una comprobación
         al final del `RUN` que **hace fallar la construcción** si alguna extensión no carga.
      2. El `conf` de Apache tiene que llamarse `zz-…`. Debian trae su `security.conf` con
         `ServerTokens OS` y carga `conf-enabled/` en orden alfabético, así que un nombre «normal»
         queda pisado. Se veía en la cabecera: seguía diciendo `Apache/2.4.68 (Debian)` con el
         endurecimiento puesto y aparentemente activo.

      **Pesa 900 MB**, y casi todo es la base de Debian con PHP: la aplicación son 108 MB. Se podría
      bajar mucho con Alpine y `php-fpm`, pero eso pide un servidor web aparte dentro del contenedor.
      Para una pieza que se quiere aburrida y auditable, el disco es más barato que la complejidad.

- [x] **3. El stack en Portainer.** **HECHO (2026-07-28)**: un solo servicio, atado a
      `127.0.0.1:8081`, en la red **`backend`** —la que ya comparten el sitio y Postgres— y llegando a
      la base por el nombre del contenedor, `postgres-postgres-1:5432`. Base y rol propios, creados en
      la instancia que ya existe.

      **`pull_policy: never` en el servicio, y no es opcional.** Sin esa línea el despliegue falla con
      `pull access denied for revive, repository does not exist or may require 'docker login'` — un
      mensaje que manda a buscar credenciales de Docker Hub cuando el problema es otro: la imagen es
      local, no está en ningún registro, y basta con que el interruptor «Re-pull image» de Portainer
      quede activado. Con `pull_policy: never` el error, si algún día falta la imagen, dice lo que
      pasa de verdad: `No such image`.

      Dos volúmenes, y conviene saber qué hay en cada uno: `var/` guarda la configuración que genera
      el instalador **con la contraseña de Postgres dentro** —si se pierde, Revive vuelve a la
      pantalla de instalación con la base llena de campañas— y `www/images/` son las creatividades que
      sube Adcio, **lo único irreemplazable del montaje**.

- [x] **4. nginx.** **HECHO (2026-07-28)**: `deploy/adserver/nginx-promo.conf`, con certificado de
      Let's Encrypt y el `server` partido por ruta. Tres cosas que costaron y quedan escritas en el
      propio archivo: `X-Frame-Options SAMEORIGIN` a nivel de servidor **rompe la entrega** —los
      anuncios van en un `iframe` y `promo.` es otro origen—, hace falta `proxy_redirect` porque
      Revive sin instalar devuelve `Location:` en `http://` y eso da un bucle de redirecciones, y el
      `http2 on;` moderno **no existe** en el nginx del VPS: usarlo tumbó `nginx -t` y dejó una
      configuración inválida en disco que habría impedido arrancar en el siguiente reinicio.

- [x] **5. Instalación y renombrado de rutas.** **HECHO (2026-07-28).** Instalado contra el Postgres
      existente, con la zona horaria dominicana para que los informes que se facturan cuadren con el
      calendario del anunciante.

      **El renombrado, que era el punto sin atajo, se midió en vez de suponerse.** Contra EasyList
      (84.414 reglas) y EasyPrivacy (56.397): de las **17 rutas de entrega, 16 estaban bloqueadas**;
      con los nombres nuevos, **ninguna**. Comprobado en producción: las nuevas responden 200 y las
      viejas dan 404.

      Tres hallazgos que no se habrían adivinado:

      1. **`.php?zoneid=` es una regla por sí sola.** Renombrar carpeta y ficheros NO bastaba: el
         parámetro también está fichado. Se resuelve poniendo `cb` delante en la etiqueta — que es el
         parámetro anti-caché que Revive ya usa en las suyas. Su formato, no un truco.
      2. **Los nombres cortos son peores que los de fábrica.** `s.php`, `a.js` y similares aparecen
         como subcadena dentro de montones de reglas ajenas. De ahí el prefijo `dgl-`.
      3. **La carpeta va a `www/pauta` y no a `/pauta`.** Los scripts hacen
         `define('MAX_PATH', __DIR__.'/../..')`: asumen estar exactamente dos niveles bajo la raíz, y
         subirlos uno los rompe en ejecución.

      Los atajos de OpenX de la raíz (`adjs.php`, `adframe.php`…) se **borran**, no se renombran: son
      puentes de compatibilidad de hace quince años, están todos fichados, y dejarlos mantendría
      abierta la puerta que se acababa de cerrar.

      **La imagen y el fichero de configuración tienen que cuadrar.** El `Dockerfile` renombra los
      ficheros en disco y la sección `[file]` de `var/*.conf.php` declara esos mismos nombres. Si
      alguien toca uno sin el otro, Revive genera etiquetas hacia ficheros que no existen.

- [x] **6. Enganchar el sitio.** **HECHO (2026-07-28)**, en la versión `1.2026.8` — **sin desplegar
      todavía**. Cuatro zonas creadas en Revive y los **trece huecos** de las plantillas conectados con
      una etiqueta, `{% anuncio zona ancho alto %}`.

      **CON `iframe` Y NO CON LA ETIQUETA DE JAVASCRIPT DE REVIVE.** Es la decisión de seguridad más
      importante del montaje. La etiqueta que ellos sugieren es JavaScript **en línea** con
      `document.write`, y usarla habría costado dos cosas caras: `'unsafe-inline'` en `script-src`
      —que tira abajo la CSP entera— y permiso de ejecución para un PHP público en TODAS las páginas.
      Con el `iframe`, el anuncio vive en su propio documento, **el servidor de anuncios no puede
      tocar el nuestro**, y la política solo tuvo que abrir `frame-src`. `script-src` sigue en
      `'self'` a secas. Para banners de venta directa no se pierde nada.

      **Cuatro zonas y no trece**, una por posición-y-medida: `Superior 728x90` (1), `Inferior
      728x90` (2), `Portada lateral 300x250` (3) y `Líderes torre 300x600` (4). Cabecera y pie van
      separadas porque **no valen lo mismo** —la de arriba se ve sin bajar— y mezclarlas obligaría a
      cobrar igual por las dos. Vender «solo la portada» no necesita más zonas: se hace con los
      conjuntos de reglas de entrega de Revive, limitando la campaña por URL.

      **Apagado por defecto.** Sin `ADSERVER_URL` los huecos siguen mostrando el recuadro rayado de
      maqueta, que mide exactamente lo mismo que el anuncio — así el diseño se prueba en desarrollo
      con las medidas reales y nadie cuenta impresiones de sí mismo recargando la portada.

      Al desplegar hay que añadir al stack, con las dos mitades de Portainer de siempre:

      ```
      ADSERVER_URL=https://promo.dominicanosengrandesligas.com
      ```

---

## Lo que hay que recordar cuando esté funcionando

**La CSP lo va a bloquear en silencio.** El sitio manda `script-src 'self'` desde el 2026-07-27, así
que hasta que `promo.dominicanosengrandesligas.com` esté en esa lista, la etiqueta no carga: el hueco
se queda vacío y el único sitio donde se explica es la consola del navegador. Ver `core/csp.py`.

**Las páginas legales cambian.** Hoy la política de cookies dice que quien solo navega no recibe
ninguna, y hay una prueba que lo sostiene (`tests/test_legal.py`). Revive puede servir sin cookies,
pero **el límite de frecuencia las necesita**: si se usa esa función, hay que reescribir la página y
montar el cartel de consentimiento. Decidirlo a conciencia, no descubrirlo.

**La prueba de terceros se va a caer, y a propósito.**
`test_el_sitio_publico_no_pide_nada_a_terceros` exige que el único externo sea el declarado en
`settings.ANALITICA_URL`. Al añadir el servidor de anuncios hay que ampliarla **nombrando el nuevo
origen**, no relajándola: el día que entre un cuarto script, alguien tiene que enterarse.

**El respaldo tiene que incluir la base de Revive y sus creatividades.** `deploy/respaldo.sh` vuelca
hoy solo la base `dglweb`. Al vivir Revive en la misma instancia de Postgres, añadirla es una línea —
pero hay que acordarse, porque un servidor de anuncios sin sus campañas es un servidor vacío, y las
imágenes que suba Adcio solo existen en su volumen.

**Y hay que mantenerlo al día.** Es la pieza más expuesta del VPS. Conviene vigilar las publicaciones
de Revive y no dejar pasar las de seguridad.
