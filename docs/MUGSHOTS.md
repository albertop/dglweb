# Los retratos de los peloteros

Cómo se actualizan las fotos que salen en la portada, en el perfil y en las tarjetas de artículo.

**Lo que hay que saber antes que nada: los retratos NO están dentro de la imagen de Docker.** Viven
en una carpeta del VPS que el contenedor monta tal cual. Por eso actualizarlos no es un despliegue —
no hay que reconstruir nada, ni correr `estaticos.sh`, ni recrear el stack. Se copian los archivos y
ya están en el aire.

Están fuera de la imagen a propósito, y también fuera de git (`.gitignore`) y del contexto de build
(`.dockerignore`): son 1.968 PNG que pesan del orden de 40 MB y cambian por su cuenta, sin relación
con las versiones del código. Meterlos en la imagen obligaría a un despliegue entero cada vez que
MLB le cambia la foto a un pelotero.

---

## 1. Bajarlas (en tu máquina)

```powershell
pwsh ./static_data/scripts/download_mugshots.ps1
```

Salen del CDN de MLB (`midfield.mlbstatic.com/v1/people/{id}/spots/{tamaño}`) y caen en dos carpetas,
una por resolución:

```
static/img/mugshots/120/<player_id>.png     los widgets de la portada
static/img/mugshots/360/<player_id>.png     la ficha del jugador
```

Hoy son **984 archivos en cada una**, uno por pelotero del maestro dominicano.

**Cada corrida vuelve a bajarlas todas, y es a propósito.** MLB cambia el retrato cuando el pelotero
cambia de equipo o de temporada, y una foto vieja no se distingue de una buena mirando el disco. Si
una corrida se cortó a la mitad, `-SoloFaltantes` baja únicamente lo que falta.

---

## 2. Subirlas al VPS con XFTP

**Carpeta destino: `/srv/dglweb-datos/mugshots/`**

Dentro tiene que quedar la misma estructura de dos carpetas que en local:

```
/srv/dglweb-datos/mugshots/120/<player_id>.png
/srv/dglweb-datos/mugshots/360/<player_id>.png
```

En XFTP, panel izquierdo (local) `static/img/mugshots/`, panel derecho (remoto)
`/srv/dglweb-datos/mugshots/`. Arrastra **las carpetas `120` y `360`**, no su contenido suelto:
soltar los PNG directamente en la raíz dejaría las fotos donde nadie las busca y el sitio seguiría
enseñando huecos sin dar ningún error.

**Sobrescribir es lo correcto.** El nombre del archivo es el `player_id`, así que la foto nueva de un
pelotero pisa a la vieja. Cuando XFTP pregunte, «Sobrescribir todo».

**Transferencia binaria, no ASCII.** Son PNG. XFTP lo detecta solo por la extensión, pero si tienes
el modo forzado a ASCII en las opciones, los archivos llegan corruptos y el navegador enseña la
imagen rota. Es el único error de este proceso que no salta a la vista.

Son ~2.000 archivos pequeños, así que la subida tarda más por la cantidad que por el peso. Es normal.

### Si prefieres línea de comandos

```bash
rsync -av --delete static/img/mugshots/ usuario@vps:/srv/dglweb-datos/mugshots/
```

`--delete` deja el destino idéntico al origen y limpia los retratos de peloteros que ya no están.
Sin él, se acumulan.

---

## 3. Permisos, y esto sí hay que hacerlo

```bash
chmod -R a+rX /srv/dglweb-datos/mugshots
```

El contenedor corre **sin privilegios** y monta la carpeta en solo lectura, así que un archivo que
llegue sin permiso de lectura para todos es invisible para el sitio aunque esté ahí. XFTP conserva
los permisos del origen o aplica los de la máscara del servidor, que no siempre son los que hacen
falta. Cuesta un segundo y ahorra un rato de buscar por qué una foto no sale.

---

## 4. Comprobar

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://dominicanosengrandesligas.com/static/img/mugshots/120/405395.png
```

Ese es el retrato de Albert Pujols; tiene que dar **200**. Es una de las tres rutas de imagen del
checklist de `PRUEBAS_DESPLIEGUE.md`, y la que confirma que nginx encuentra la carpeta.

Para verlo con los ojos, la portada: los widgets de Destacados y de rachas van llenos de retratos.

**Si tú ves una foto vieja y el `curl` da 200, no es un fallo.** nginx manda `Cache-Control` de 30
días y estos archivos **no llevan hash en el nombre** — se sobrescriben con el mismo. Tu navegador
guarda la anterior; un visitante nuevo ve la nueva al instante. Con Ctrl+F5 se confirma.

---

## 5. Por qué no hace falta tocar el contenedor

Hay dos caminos y ninguno pasa por la imagen:

**Servir el archivo** lo hace nginx directo, sin despertar a Django
(`deploy/nginx-dglweb.conf`):

```nginx
location /static/img/mugshots/ {
    alias /srv/dglweb-datos/mugshots/;
}
```

**Decidir si la foto existe** lo hace Django leyendo el disco en cada petición: `mugshots.existe()`
hace un `is_file()` sobre la carpeta montada. No hay índice, ni caché, ni nada que refrescar — por
eso un archivo nuevo aparece en la siguiente recarga de la página.

Y ese `is_file()` mira **la carpeta de origen y no `STATIC_ROOT`**, que es la sutileza que hace que
todo esto funcione: `collectstatic` corre al construir la imagen, cuando los retratos todavía no
existen, así que en producción no están en `staticfiles/`. Django pregunta por la misma carpeta que
nginx acaba sirviendo, de modo que la respuesta vale para lo que el navegador va a pedir después.

El montaje está en `deploy/stack.yml`:

```yaml
- /srv/dglweb-datos/mugshots:/app/static/img/mugshots:ro
```

---

## 6. Cuándo toca hacerlo

No hay un calendario, y tampoco un trabajo programado que lo haga solo. Los tres momentos en que vale
la pena:

- **Empezando la temporada**, cuando MLB renueva los retratos con el uniforme nuevo.
- **Después de una racha de debutantes.** Un pelotero que no está en la carpeta sale sin foto: la
  etiqueta `data-quitar-si-falta` borra la imagen rota, así que no se ve un icono partido, pero
  tampoco se ve al pelotero.
- **Cuando alguien cambia de equipo** y su foto sigue con la camiseta anterior.

Nada se rompe por tenerlas viejas. Simplemente se ven desactualizadas.
