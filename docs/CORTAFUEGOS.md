# El cortafuegos del VPS — verificado el 2026-07-30

Lo que hay, por qué está bien, y **la regla que es fácil romper sin darse cuenta**.

## La regla que no se puede romper

> **Todo contenedor publica en `127.0.0.1`, nunca en `0.0.0.0`.**

Y no es una preferencia de estilo: **Docker se salta ufw**. Cuando un contenedor publica un puerto con
`-p 5432:5432`, Docker escribe sus propias reglas en `iptables` *por delante* de las de ufw, así que
ese puerto queda abierto a Internet **aunque `ufw status` diga que todo está bloqueado**.

Es de los fallos más caros que existen porque la herramienta te dice que estás protegido. El día que
alguien añada un contenedor al stack y escriba `-p 8080:8080` en vez de `-p 127.0.0.1:8080:8080`, lo
habrá expuesto — y `ufw status` seguirá diciendo `deny (incoming)`.

**Cómo se comprueba** (las dos cosas, no una):

```bash
sudo ss -tlnp | grep -vE "127\.0\.0\.1|\[::1\]"   # qué escucha DE VERDAD hacia fuera
docker ps --format '{{.Names}}\t{{.Ports}}'        # qué publicó Docker
```

En el primero solo pueden salir **80, 443 y 22**. En el segundo, todo prefijado con `127.0.0.1:`.

## Cómo estaba el 2026-07-30

Los nueve contenedores, todos correctos:

    dglweb-web-live   127.0.0.1:3004
    revive            127.0.0.1:8081
    mlb-proxy-api     127.0.0.1:3003
    pgadmin           127.0.0.1:5050
    sabertables       127.0.0.1:3001
    sixdegrees        127.0.0.1:3002
    portainer         127.0.0.1:9000 / 9443
    postgres          5432/tcp        ← ni siquiera al host
    dglweb-scheduler  (ninguno)

**Postgres es el mejor caso posible**: `5432/tcp` sin prefijo de host significa que el puerto no se
publica en absoluto — existe solo dentro de la red de Docker, que es donde lo alcanzan dglweb y Revive.
Ni con ufw apagado sería accesible desde fuera. Si algún día hace falta llegar con un cliente desde el
portátil, la salida NO es publicarlo: es un túnel SSH.

Política de ufw: `deny (incoming)`, `allow (outgoing)`, `deny (routed)`. Abiertos 22 (con `LIMIT`, más
la IP del dueño explícita), 80 y 443.

## Tailscale es la salida de emergencia

`sshd` escucha en `0.0.0.0`, así que también responde por la interfaz del tailnet. Eso importa por una
razón concreta: **si fail2ban llegara a banear la IP del dueño** —o si esa IP cambia y deja de coincidir
con la de `ignoreip`— se puede entrar igual por Tailscale.

Es lo que hace que el riesgo de quedarse fuera sea bajo, y lo que haría razonable cerrar el 22 al mundo
si algún día molesta la fuerza bruta constante (había 14 IPs baneadas por `sshd` ese día). No se hizo:
con `LIMIT` más fail2ban el riesgo ya es aceptable, y cerrarlo añade una dependencia de que Tailscale
funcione el día que haga falta.

## Lo que fail2ban añade encima

ufw bloquea puertos; fail2ban bloquea **IPs que se portan mal en los puertos abiertos**. Las reglas
aparecen en `ufw status` como `REJECT IN … # by Fail2Ban`. Ver `deploy/fail2ban-nginx.local`.

El mismo día en que se arreglaron las jails de nginx, la primera IP cazada fue un escáner de webshells
(`/xstelth.php`, `/wp-load.php`) — detectada, contada y metida en el cortafuegos en minutos.
