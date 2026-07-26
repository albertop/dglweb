# =====================================================================================
# Las fotos de los peloteros — descarga desde el CDN de MLB
# =====================================================================================
#
# QUÉ BAJA, Y POR QUÉ DE AHÍ
# --------------------------
# El retrato recortado de cada pelotero, el mismo que MLB usa en sus propias tablas de líderes.
# Sale de `midfield.mlbstatic.com/v1/people/{id}/spots/{tamaño}`.
#
# Medido contra los candidatos que existen, antes de elegir:
#
#   midfield spots/120    PNG   6.4 KB   fondo TRANSPARENTE, cuadrada 120×120
#   midfield spots/360    PNG  37.4 KB   idem, 360×360
#   securea head_shot     JPG  20.7 KB   fondo gris, una sola resolución
#   img.mlbstatic w_426   JPG  89.3 KB   fondo gris, rectangular 426×640
#
# Gana `midfield/spots`: es la única con fondo transparente —se apoya sobre cualquier color de
# tarjeta sin recorte blanco alrededor— y la única donde el tamaño es un parámetro de la URL, así que
# pedir otra resolución no cuesta trabajo nuevo. Acepta cualquier número y devuelve exactamente ese
# cuadrado; está medido de 60 a 720.
#
# NO sale del endpoint `/content` del juego. Ahí también hay imágenes, pero son las PORTADAS DE LOS
# VIDEOS: fotogramas 16:9 de la jugada, con títulos del tipo «… - thumbnail». No son retratos.
#
# DÓNDE CAEN
# ----------
# `static/img/mugshots/<tamaño>/<player_id>.png`. Una carpeta por resolución, no un sufijo en el
# nombre: así el widget arma la ruta cambiando un solo segmento, y agregar un tamaño mañana es crear
# una carpeta y no renombrar nada.
#
# Las imágenes NO se versionan ni se hornean en la imagen de Docker (ver .gitignore y .dockerignore).
# La carpeta local se monta dentro del contenedor tal cual, así que dejarlas acá basta para que el
# sitio las sirva — ver `docker-compose.yml`.
#
# Correrlo REFRESCA todo: cada corrida vuelve a bajar las 637, porque para eso está. MLB actualiza
# los retratos cuando el pelotero cambia de equipo o de temporada, y una foto vieja no se distingue
# de una buena mirando el disco. Con `-SoloFaltantes` se baja únicamente lo que no está, que sirve
# para rellenar una corrida que se cortó a mitad.
# =====================================================================================

[CmdletBinding()]
param(
    # Baja únicamente lo que falta. Por defecto se refrescan TODAS: MLB actualiza los retratos cuando
    # el pelotero cambia de equipo o de temporada, y una foto vieja no se distingue de una buena
    # mirando el disco. Esta opción es para rellenar una corrida que se cortó, no para el uso normal.
    [switch]$SoloFaltantes,
    # Solo dice qué haría. Útil para ver el tamaño de la descarga antes de lanzarla.
    [switch]$Simular
)

[System.Threading.Thread]::CurrentThread.CurrentCulture = [System.Globalization.CultureInfo]::InvariantCulture

# --- Configuración -------------------------------------------------------------------
$SqlServer = "localhost"          # ⚠️ AJUSTAR: la instancia donde vive DGL
$Database  = "DGL"
$Destino   = "$PSScriptRoot\..\..\static\img\mugshots"

# Los dos tamaños que el sitio usa, uno por sitio donde aparece la foto:
#
#   120  los widgets de la portada — se muestra a ~60px, así que cubre pantallas retina
#   360  el perfil del jugador     — se muestra a ~180px, misma cuenta
#
# Cada uno es el doble de lo que se ve en pantalla, que es lo que hace que no se vean borrosas en un
# monitor denso. Si mañana hace falta otro, se agrega acá y el script crea la carpeta solo.
#
# Peso estimado con ~300 peloteros: unos 13 MB en total. Nada que justifique optimizar más.
$Tamanos = @(120, 360)

# --- La lista de peloteros -----------------------------------------------------------
# Solo los que vieron acción en las últimas dos temporadas. Bajar los 1.000 y pico del maestro
# histórico sería descargar cientos de retratos de gente que el sitio no va a mostrar en un widget de
# la temporada en curso — y de muchos de ellos MLB ni tiene foto.
#
# Solo el id: la vista trae más columnas, pero acá lo único que se necesita es con qué armar la URL.
$Query = @"
SELECT DISTINCT [player_id]
FROM   [dbo].[v_dglweb_players_played_last_2_years]
WHERE  [player_id] IS NOT NULL
ORDER BY [player_id];
"@

# --- Consulta ------------------------------------------------------------------------
# ADO.NET y no `Invoke-Sqlcmd`, igual que los demás export: ese cmdlet vive en el módulo `SqlServer`,
# que no viene instalado por defecto. ADO.NET es parte de .NET y funciona sin preparar nada.
$conexion = "Server=$SqlServer;Database=$Database;Integrated Security=True;TrustServerCertificate=True"

Write-Host "Consultando $Database en $SqlServer..."
try {
    $cn = New-Object System.Data.SqlClient.SqlConnection $conexion
    $cn.Open()
    $cmd = $cn.CreateCommand()
    $cmd.CommandText = $Query
    $cmd.CommandTimeout = 300
    $tabla = New-Object System.Data.DataTable
    $tabla.Load($cmd.ExecuteReader())
}
catch {
    Write-Error "No se pudo consultar SQL Server: $_"
    exit 1
}
finally {
    if ($cn -and $cn.State -eq 'Open') { $cn.Close() }
}

if ($tabla.Rows.Count -eq 0) { Write-Error "La consulta no devolvio filas."; exit 1 }
Write-Host "$($tabla.Rows.Count) peloteros con accion en las ultimas dos temporadas."

# --- Descarga ------------------------------------------------------------------------
foreach ($t in $Tamanos) {
    $carpeta = Join-Path $Destino $t
    if (-not (Test-Path $carpeta)) { New-Item -ItemType Directory -Path $carpeta -Force | Out-Null }
}

# Una sesión reutilizada en vez de una conexión por foto: son cientos de descargas y el handshake TLS
# repetido cuesta más que las imágenes.
$ProgressPreference = 'SilentlyContinue'   # la barra de Invoke-WebRequest hace esto tres veces más lento

$bajadas = 0; $saltadas = 0; $fallidas = @{}
$peloteros = $tabla.Rows.Count
$vistos = 0

foreach ($fila in $tabla.Rows) {
    $id = $fila.player_id
    $vistos++

    foreach ($t in $Tamanos) {
        $ruta = Join-Path (Join-Path $Destino $t) "$id.png"

        if ($SoloFaltantes -and (Test-Path $ruta)) { $saltadas++; continue }

        $url = "https://midfield.mlbstatic.com/v1/people/$id/spots/$t"
        if ($Simular) { Write-Host "  [simulado] $url -> $ruta"; continue }

        try {
            Invoke-WebRequest -Uri $url -OutFile $ruta -UseBasicParsing -TimeoutSec 20 -ErrorAction Stop
            $bajadas++
        }
        catch {
            # Que a un pelotero le falte la foto no puede tumbar la corrida: se anota y se sigue. Al
            # final se listan, que es cuando sirve saberlo.
            $fallidas[$id] = $_.Exception.Message
            if (Test-Path $ruta) { Remove-Item $ruta -Force }   # un archivo a medias es peor que ninguno
        }
    }

    # El avance se cuenta en PELOTEROS y no en descargas: «300 / 637» se entiende solo, mientras que
    # «600 / 1274» obliga a acordarse de que cada uno son dos archivos.
    #
    # Y va acá afuera, no dentro del bucle de tamaños: ahí adentro el `continue` de «ya existe» se lo
    # saltaba, así que en una segunda corrida los hitos desaparecían y el conteo parecía cortado.
    if ($vistos % 100 -eq 0) { Write-Host "  $vistos / $peloteros peloteros..." }
}

$ProgressPreference = 'Continue'

# --- Resumen -------------------------------------------------------------------------
# Se dice de qué se está hablando: son ARCHIVOS, y cada pelotero son dos. Sin eso, «bajadas 868» con
# 637 peloteros en pantalla parece una contradicción.
"{0} peloteros x {1} tamanos = {2} archivos" -f $peloteros, $Tamanos.Count, ($peloteros * $Tamanos.Count)
if ($SoloFaltantes) {
    "  bajados {0} | ya estaban {1} | sin foto en el CDN {2}" -f $bajadas, $saltadas, $fallidas.Count
} else {
    "  refrescados {0} | sin foto en el CDN {1}" -f $bajadas, $fallidas.Count
}

if ($fallidas.Count -gt 0) {
    # Sin foto no es un error del script: hay peloteros que MLB no retrata, sobre todo debutantes
    # recientes. Se listan para que el dueño decida si vale la pena buscarlas a mano.
    Write-Warning "Sin foto en el CDN de MLB: $($fallidas.Keys -join ', ')"
}
