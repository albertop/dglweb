# Rendimiento y seguridad para el lanzamiento

**Medido el 2026-07-29 sobre producción.** Todo lo de acá sale de números, no de una lista genérica
de buenas prácticas. Los números están para que dentro de un año se sepa qué era «normal».

---

## Lo primero: la foto real

| Página | Desde fuera | Dentro del contenedor | Consultas | En base |
|---|---|---|---|---|
| `/health` | 0,23 s | — | — | — |
| `/contacto/` | 0,82 s | **22 ms** | 1 | 2 ms |
| `/articulos/` | 0,95 s | **187 ms** | 19 | 45 ms |
| `/lideres/` | 0,64 s | **227 ms** | 23 | 56 ms |
| `/` | ~0,70 s | **274 ms** | 17 | 36 ms |

**El servidor va sobrado**: 4 núcleos, 4,8 Gi de RAM con 2,3 libres, carga 0,55. **La base de datos
no es el cuello**: 36-56 ms por página, con 17-23 consultas. **Python tampoco**: 140-240 ms.

Y de los 0,64 s que ve un visitante, **0,23 s son latencia de red pura** hasta el VPS — eso no se
optimiza desde acá.

> **Dos falsas alarmas, anotadas para no repetirlas.** La primera medición dio 3,2 s en la portada y
> 3,3 s en líderes, y se llegó a llamar «el problema». Eran **cachés frías**: la primera petición
> tras un despliegue arma la pizarra pidiéndosela al proxy y llena las cachés de tablas de
> referencia. Repetida, la misma página baja a 0,6 s. Medir una vez no es medir.

---

## EL problema, y es uno solo

**La portada referencia 210 recursos estáticos. De esos, 164 los sirve WhiteNoise — o sea, gunicorn.**

Y gunicorn corre con **3 workers síncronos**. Un worker síncrono atiende **una petición a la vez**,
así que esas peticiones ocupan uno de esos tres huecos cada una. Eso es lo que se cae el día del
lanzamiento — no la base, que va sobrada, ni el CPU, que está ocioso.

> ### CORRECCIÓN (2026-07-29): ese 210 estaba mal contado, y el error era mío
>
> **210 eran REFERENCIAS en el HTML, no peticiones.** La bandera dominicana aparece 19 veces y el
> escudo de Miami 15, pero el navegador pide cada URL **una sola vez**. Contados como los pide un
> navegador:
>
> | | |
> |---|---|
> | referencias en el HTML | 212 |
> | **archivos distintos** | **68** |
> | peso total, comprimido | **313,8 KB** |
> | HTML | 125,2 KB |
>
> O sea que **la página ya era ligera**, y el reparto real era 24 por nginx y 44 por gunicorn, no 44
> y 164.
>
> **Lo que NO cambia**: 44 peticiones por visitante contra 3 workers seguía siendo un problema real
> de concurrencia, y pasarlas a nginx seguía siendo lo correcto. Lo que cambia es el tamaño del
> susto, y sobre todo el punto 4 del plan, que se cae entero.

## Plan, por orden de lo que más suma

### 1. Que nginx sirva los estáticos — LA GRANDE ✅ HECHO 2026-07-29

Quita **164 de 210 peticiones** de gunicorn y las pasa a nginx, que para servir archivos es lo que
es. Los workers quedan libres para lo único que solo ellos pueden hacer: generar HTML.

Vive en dos archivos del repositorio, no solo en el servidor: `deploy/nginx-dglweb.conf` y
`deploy/estaticos.sh`.

**Medido después del cambio**, sobre producción:

| | Antes | Después |
|---|---|---|
| `site.css` lo sirve | gunicorn (WhiteNoise) | **nginx** |
| Peso en el cable | 80.701 B | **25.901 B** (`gzip_static`) |
| Escudos de equipo | gunicorn | **nginx**, comprimidos |

`gzip_static on` no comprime en cada petición: WhiteNoise ya dejó los `.gz` al lado de cada archivo
durante `collectstatic`, y nginx los manda tal cual.

**Ojo con el orden en el despliegue**: los estáticos se copian **después** de recrear el contenedor.
Al revés, el HTML nuevo pediría hashes que no están en disco — 404 en el CSS, sitio sin estilos.

> **Un defecto que se coló y salió en la comprobación.** La primera versión de este bloque ponía
> `expires 1y;` **y** `add_header Cache-Control "public, immutable"`. Las dos directivas escriben la
> misma cabecera, así que la respuesta salía con **dos `Cache-Control` distintas**. Los navegadores
> las combinan, pero una respuesta con dos cabeceras de caché contradictorias es ambigua por
> definición. Ahora hay **una sola directiva por bloque**. Nada avisó: `nginx -t` daba correcto y la
> página cargaba bien — solo apareció al mirar las cabeceras con `get_all` en vez de `get`.

> **Y una decisión aparte para los retratos: 30 días, no un año.** Esos 1.970 archivos **no llevan
> hash** en el nombre; el script de descarga del dueño los sobrescribe con el mismo nombre. Con caché
> de un año, quien ya vio a un pelotero se quedaría con el retrato viejo hasta el año siguiente. El
> resto de los estáticos sí lleva hash, y por eso ahí el año e `immutable` sí es correcto.

### 2. gunicorn: de `sync` a `gthread` ✅ HECHO 2026-07-29

Antes: **3 peticiones concurrentes como máximo en todo el sitio**. Un worker síncrono atiende UNA a
la vez, y Django no pasa su tiempo calculando sino ESPERANDO a Postgres y al proxy. Un worker
bloqueado 40 ms esperando a la base es un worker que durante esos 40 ms no atiende a nadie.

En `Dockerfile.prod`:

```dockerfile
     "--workers", "4",      "--worker-class", "gthread",      "--threads", "4", ```

**4 × 4 = 16 peticiones concurrentes**, cinco veces más. Comprobado antes de construir la imagen: la
clase resuelve a `gunicorn.workers.gthread.ThreadWorker`.

Y es casi gratis en memoria: los hilos comparten el proceso, así que pasar de 3 a 16 concurrentes
cuesta UN worker más, no trece. `--preload` ya deja compartidos los ~90 MB de Django y Wagtail.

**Lo que hace que sea seguro** y no una fuente de datos corruptos: las dos cachés aguantan hilos
—`LocMemCache` usa un cerrojo, la compartida vive en la base— y Django guarda la conexión a Postgres
en almacenamiento **por hilo**, así que dos hilos nunca comparten un cursor.

Cuatro workers y no los nueve de la fórmula `(2 × núcleos) + 1`: esa fórmula es para saturar CPU, y
acá el trabajo es esperar E/S. Con 4,8 Gi de RAM y Postgres al lado, nueve procesos es apretar sin
ganar.

> **Pendiente de medir en producción: `CONN_MAX_AGE`.** Hoy está en **0**, así que cada petición abre
> y cierra su conexión a Postgres. Medirlo en DEV no vale —la base de DEV está en 10.0.0.39, al otro
> lado de la red, y sus 51 ms son latencia, no coste de conexión—. En producción la base es un
> contenedor en el mismo host. Si abrir cuesta más de ~5 ms, subirlo a 60 se paga solo; con 16 hilos
> serían hasta 16 conexiones persistentes, holgado contra las 100 de `max_connections` (hoy se usan
> 9).

### 2b. Conexiones persistentes a Postgres — HECHO 2026-07-29

Salió de perseguir un número que no cuadraba. Abrir una conexión a Postgres, **en producción**,
costaba 32,9 ms. Para una base que está en el mismo servidor eso es absurdo, así que se partió en
tres:

| | |
|---|---|
| resolver el nombre | 0,8 ms |
| abrir el socket TCP | 1,2 ms |
| **la conexión entera** | **32,9 ms** |

O sea que **31 de los 33 ms no son red**. Se descartó el TLS —Postgres tiene `ssl` apagado, y
conectar con `sslmode=disable` da lo mismo: 30,1 contra 30,9 ms—. Lo que queda son las dos cosas que
no se pueden quitar: `scram-sha-256` derivando la clave con 4.096 iteraciones a los dos lados, y
**Postgres bifurcando un proceso nuevo por cada conexión**. Es literalmente la razón por la que
existen los pools de conexiones.

Con `CONN_MAX_AGE = 0` —el valor de fábrica— eso se pagaba **en cada petición**: 33 ms sobre los 274
de la portada, un 12% del tiempo, gastado en volver a presentarse.

```python
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
```

**Las cuentas de Postgres**: con 4 workers y 4 hilos son como mucho 16 conexiones vivas —Django
guarda una por hilo—, contra las 100 de `max_connections`. Hoy se usan 9 en todo el servidor
contando pgAdmin y Revive.

> **Se descartó escribir la IP a mano** en vez del nombre `postgres`. Ahorraba 0,8 ms —el 2,4% del
> coste— a cambio de que el sitio dejara de conectar el día que Docker le asigne otra IP al
> contenedor, cosa que pasa al recrear el stack o al reiniciar el servidor. Y con las conexiones
> persistentes el nombre se resuelve como mucho 16 veces por minuto en vez de una por visita, así
> que esos 0,8 ms desaparecen igual.

> **El error que casi se despliega, y por qué había que probarlo.** `CONN_HEALTH_CHECKS` se escribió
> primero suelto en el módulo de settings. Django **lo ignora en silencio** —es por base de datos, va
> DENTRO de `DATABASES`— y mientras tanto `settings.CONN_HEALTH_CHECKS` devuelve `True` tan
> tranquilo. Sin él, `CONN_MAX_AGE` cambia un problema de velocidad por uno de caídas: la conexión
> guardada sobrevive en Django pero no en Postgres, y el primer visitante después de un reinicio de
> la base se lleva un 500.
>
> No lo detectó ninguna herramienta. Se detectó **matando una conexión a propósito** desde el
> servidor con `pg_terminate_backend` y volviendo a consultar: `OperationalError: terminating
> connection due to administrator command`. Eso es ahora `tests/test_conexiones_persistentes.py`.

### 3. Postgres — REDIMENSIONADO 2026-07-29, hacia abajo

El plan original decía `shared_buffers = 1GB`, `effective_cache_size = 3GB` y
`maintenance_work_mem = 256MB`. **Casi todo sobra**, y medirlo antes ahorró reservar memoria que no
hacía falta:

| | |
|---|---|
| **la base entera pesa** | **228 MB** |
| RAM total / disponible | 4.917 MB / 2.387 MB |
| swap en uso | **474 MB** |
| tiempo en base por página | 36-56 ms, 17-23 consultas |

Con la base entera en 228 MB, pedir 1 GB de `shared_buffers` es reservar **cuatro veces la base** —y
con el swap ya en uso—. Y no hay problema de E/S que resolver: 2 ms por consulta.

Lo que queda, y el primero es el único que cambia algo de verdad:

```sql
-- CAMBIA DECISIONES DEL PLANIFICADOR. En 4.0 (el defecto) Postgres cree que leer una página al azar
-- cuesta 4 veces más que una secuencial: cierto en disco giratorio, falso en SSD. Con 4.0 descarta
-- índices que sí convienen.
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET work_mem = '16MB';        -- hoy 4 MB
ALTER SYSTEM SET shared_buffers = '256MB'; -- hoy 128 MB. 256 caben los 228 con margen para crecer
```

`shared_buffers` pide reiniciar el contenedor; los otros dos, `SELECT pg_reload_conf()`. Y lo hace el
superusuario `postgres`, no `dglweb`, que no lo es.

> **Queda dentro del volumen, no en el repositorio.** `ALTER SYSTEM` escribe en
> `postgresql.auto.conf` dentro de los datos: sobrevive a reinicios y a recrear el contenedor, pero
> es invisible en Portainer y en un diff. Va contra cómo está todo lo demás. Moverlo a `command:` en
> el compose de Postgres es la tarea pendiente.

### 4. Reducir los recursos — DESCARTADO 2026-07-29, con números

Este punto existía por el error de conteo de arriba. Con la medición correcta **no hay nada que
hacer acá**, y vale más cerrarlo que dejarlo abierto dando mala conciencia:

- **El sprite de escudos no compensa.** Son 32 SVG distintos y **57,6 KB en total ya comprimidos**.
  Por HTTP/2 van multiplexados por la misma conexión y se cachean un año. Juntarlos en un sprite
  ahorra 31 peticiones baratas a cambio de complicar las plantillas de verdad.

- **El `loading="lazy"` ya está donde tiene que estar.** De las 198 `<img>` de la portada, 44 lo
  llevan y son **exactamente los retratos**. Las 154 que no lo llevan son **iconos de 20×20 y
  banderitas de 17×11**: ponerles `lazy` sería contraproducente —le da trabajo al navegador y
  provoca saltos de maquetación— para ahorrar unos pocos KB.

Lo más pesado que queda es Bootstrap: 30,1 KB de CSS y 23,1 KB de JS, o sea **53 de los 314 KB**.
Recortar lo que no se usa se puede, pero es un cambio con riesgo de romper estilos por todo el sitio
a cambio de unos KB en una página que ya es ligera. **No antes del lanzamiento.**

---

## Seguridad

**La buena noticia: dglweb es el mejor configurado de los tres sitios.** Django ya manda, medido:

```
Content-Security-Policy: default-src 'self'; script-src 'self' https://cloud.umami.is; …
X-Frame-Options: DENY
Strict-Transport-Security: max-age=31536000
X-Content-Type-Options: nosniff
Referrer-Policy: same-origin
Cross-Origin-Opener-Policy: same-origin
```

Más el CMS cerrado por IP (2026-07-29) y el panel de anuncios igual.

**Lo que falta:**

- [x] **Límites de peticiones — HECHO 2026-07-29.** dglweb no tenía ninguno, al revés que pgAdmin,
      Portainer y sabertables. Están en `deploy/nginx-limites.conf` (las zonas, contexto `http`) y se
      aplican en `deploy/nginx-dglweb.conf`.

      | zona | ritmo | arranque | dónde |
      |---|---|---|---|
      | `dgl_html` | 20/s | 40 | `location /` — las caras, las que ocupan un hilo |
      | `dgl_estaticos` | 300/s | 600 | `/static/`, `/media/`, retratos |

      **Por qué tan altos, y no es pereza.** Una visita pide 68 archivos y por HTTP/2 llegan casi de
      golpe. Y sobre todo: **CGNAT**. En República Dominicana muchísimos usuarios móviles comparten
      una IP pública, así que un límite ajustado no bloquea a un atacante — bloquea a medio Claro.
      Estos números están para parar UN cliente que se vuelve loco, no para regular a la gente.

      **El CMS queda fuera a propósito**: ya está cerrado por IP, y el panel de Wagtail dispara
      muchas llamadas seguidas al guardar. Limitar al único usuario autorizado es estorbar sin
      proteger.

      **Y devuelven 429, no el 503 de fábrica.** No es un detalle: 429 significa «vas muy rápido,
      vuelve» y Googlebot baja el ritmo. 503 significa «el servidor está roto», y repetido hace que
      Google saque páginas del índice — un pico de tráfico podría costar posiciones de búsqueda.

- [x] **`includeSubDomains` en la HSTS — HECHO 2026-07-29.** Estaba apagado por una razón buena:
      encenderlo con un subdominio sin TLS lo deja **inaccesible durante un año**, porque el navegador
      se niega a hablarle por HTTP y ya no hay forma de decirle que sí.

      Así que se comprobó cuáles existen de verdad antes de tocarlo. Bajo `dominicanosengrandesligas.com`
      hay **exactamente dos**, y los dos redirigen HTTP→HTTPS con un 301:

      | subdominio | qué es | HTTP | HTTPS |
      |---|---|---|---|
      | `www.` | el mismo sitio | 301 | 200 |
      | `promo.` | el panel de anuncios (Revive) | 301 | 302 al panel |

      Los otros dominios del servidor —`sabertables.com`, `baseballsixdegrees.com`, `prdm0.com`— **no
      son subdominios de este**, así que la cabecera no los toca.

      **Lo que obliga de aquí en adelante**: cualquier subdominio nuevo nace con TLS o no funciona. Un
      `staging.` levantado deprisa por HTTP se verá inaccesible desde cualquier navegador que haya
      entrado al sitio. No es un problema —Let's Encrypt es gratis y automático— pero hay que saberlo
      antes, no descubrirlo.

      **`preload` NO, y es a propósito.** Es otra cosa: mete el dominio en una lista que viene
      COMPILADA dentro de Chrome, Firefox y Safari. Salir de ahí tarda meses y depende de que otros
      publiquen versiones nuevas del navegador. Lo protege `tests/test_cabeceras_seguridad.py`, que
      falla si alguien lo enciende — para que sea una decisión y no un descuido de una línea.

- [x] **fail2ban sobre los registros de nginx** — hecho el 2026-07-30. El filtro, la jail y la línea
      base están versionados en `deploy/fail2ban/`, y `docs/RESTAURAR.md` lleva los comandos de
      instalación. Lo que queda no es montarlo:

- [ ] **Observar unos días qué captura `nginx-404-scan`** antes de subirle la mano. Está puesto para
      cazar escaneos, pero el filtro activo casa CUALQUIER 404 —el estrecho quedó comentado al
      lado— así que conviene mirar el registro de baneos antes de darlo por afinado.
