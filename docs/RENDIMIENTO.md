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

```
  mugshots (nginx, desde disco)     44
  resto (WhiteNoise → gunicorn)    164   ← de los cuales 153 son imágenes
```

Y gunicorn corre con **3 workers síncronos**. Un worker síncrono atiende **una petición a la vez**.

Así que **una sola visita a la portada genera 164 peticiones que ocupan uno de esos tres workers cada
una**. Diez visitantes simultáneos son 1.640 peticiones peleándose por tres huecos. Eso es lo que se
cae el día del lanzamiento — no la base, que va sobrada, ni el CPU, que está ocioso.

Hoy no se nota porque el sitio no tiene tráfico. Por eso no aparece en ninguna medición de arriba.

---

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

### 2. gunicorn: de `sync` a `gthread`

Hoy: **3 peticiones concurrentes como máximo**. Con hilos, cada worker atiende varias a la vez
mientras espera a la base o al proxy, que es donde Django pasa la mayor parte del tiempo.

```dockerfile
     "--workers", "4", \
     "--worker-class", "gthread", \
     "--threads", "4", \
```

**4 × 4 = 16 peticiones concurrentes**, cinco veces más que hoy. Y casi gratis en memoria: los hilos
comparten el proceso, así que no multiplica los ~90 MB de código de Django y Wagtail que `--preload`
ya deja compartidos.

Cuatro workers y no los nueve de la fórmula `(2 × núcleos) + 1`: esa fórmula es para saturar CPU, y
acá el trabajo es esperar E/S. Con 4,8 Gi de RAM y Postgres al lado, nueve procesos es apretar sin
ganar.

### 3. Postgres, que corre con la configuración de fábrica

Los valores por defecto de Postgres están pensados para arrancar en cualquier máquina, no para
aprovechar una. Con 4,8 Gi y la base compartida con Revive:

```
shared_buffers = 1GB              # por defecto 128MB
effective_cache_size = 3GB        # le dice al planificador cuánta caché del sistema puede contar
work_mem = 16MB                   # por defecto 4MB; los ORDER BY de líderes se agradecen
maintenance_work_mem = 256MB      # los VACUUM y la creación de índices
random_page_cost = 1.1            # por defecto 4.0, que asume disco giratorio. El VPS es SSD.
```

**`random_page_cost` es el que más cambia decisiones**: con 4.0 el planificador evita índices que
sí convienen en SSD.

No es urgente —la base responde en 36-56 ms— pero es lo que sostiene el crecimiento.

### 4. Reducir los 210 recursos

Lo anterior hace que 210 peticiones dejen de doler. Esto las quita de en medio:

- **153 son imágenes**: retratos de peloteros y escudos de equipo. Los escudos son 30 SVG que se
  repiten en toda la página; un sprite los deja en uno.
- **`loading="lazy"`** en los retratos que caen bajo el pliegue.

Es trabajo de plantillas y no de infraestructura, así que va después.

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

- [ ] **Límites de peticiones.** dglweb **no tiene ninguno**, al revés que pgAdmin, Portainer y
      sabertables. Con tráfico de lanzamiento eso es tanto un asunto de seguridad como de
      estabilidad: un rastreador agresivo o un pico puede tumbar el sitio sin mala intención.

      Se monta con `limit_req_dry_run on` primero —evalúa y registra sin bloquear— y se ajusta con
      tráfico real. Poner un número a ojo antes de tener visitantes es la forma segura de estrangular
      a los primeros.

      **Y el límite NO puede ser uniforme**: la portada referencia 210 recursos, así que un visitante
      normal hace 210 peticiones en dos segundos. Un límite pensado para páginas HTML mataría a
      cualquiera. Va por zonas: una para el HTML y otra, mucho más holgada, para `/static/`.

- [ ] **`includeSubDomains` en la HSTS.** Hoy falta. Añadirlo cubre también
      `promo.dominicanosengrandesligas.com`, que ya va por HTTPS. Es una decisión con vuelta atrás
      lenta —el navegador recuerda un año— así que se hace a conciencia.

- [ ] **fail2ban sobre los registros de nginx**, para que los escaneos repetidos se corten en el
      cortafuegos y no lleguen a gastar workers.
