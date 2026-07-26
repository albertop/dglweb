# =====================================================================================
# Calendario de temporadas — export de DGL para el sitio
# =====================================================================================
#
# QUÉ ES ESTA TABLA
# -----------------
# Una fila por temporada con sus fechas: cuándo abre, cuándo termina la serie regular, cuándo es el
# Juego de Estrellas, cuándo arranca octubre y cuándo cierra todo. Es lo que permite responder
# preguntas como "¿este juego fue de serie regular o de postemporada?" sin adivinar por el mes.
#
# UPSERT, NO TRUNCATE — Y ESTO IMPORTA
# ------------------------------------
# Es el único dataset de apoyo que TAMBIÉN se edita a mano en el Backoffice: son pocas filas, y
# cuando MLB mueve una fecha conviene corregirla sin esperar a que alguien corra este script.
#
# Por eso la carga respeta lo que ya está: pisa las temporadas que vienen en el CSV y deja en paz
# las demás. Truncar borraría justamente esas correcciones.
#
# La contracara, que conviene tener presente: con truncate una fila mala desaparece en la carga
# siguiente; con upsert SE QUEDA, porque nada la borra. Por eso el import es más estricto acá —
# rechaza fechas fuera de orden y más de una temporada marcada como en curso.
#
# CÓMO SE USA
# -----------
#   1. Correr este script (necesita acceso a DGL en SQL Server).
#   2. Subir el CSV en el Backoffice: Datos de apoyo -> seasons_dates -> Cargar.
#   3. La pantalla compara contra lo que ya está ANTES de escribir nada.
#
# Para editar una fecha suelta no hace falta nada de esto: Backoffice -> Calendario de temporadas.
#
# Ver docs/DATOS_DE_APOYO.md y docs/MOTOR_DATOS_APOYO.md.
# =====================================================================================

# --- Nada de formato regional --------------------------------------------------------
# Esta tabla es casi toda fechas, así que es la que más expuesta está al problema que ya nos pasó con
# `dom_players`: `Export-Csv` las escribe con la cultura de la maquina y «7/6/1987» significa una
# cosa en una y otra en otra. Dos defensas:
#   1. Cada fecha se convierte a ISO EN SQL (estilo 23), abajo en la consulta. Esa es la real.
#   2. Y ademas cultura invariante en el hilo, por si manana se suma una columna con formato.
# El import rechaza cualquier cosa que no sea ISO, asi que la ambiguedad no puede entrar a la base.
[System.Threading.Thread]::CurrentThread.CurrentCulture = [System.Globalization.CultureInfo]::InvariantCulture

# --- Configuración -------------------------------------------------------------------
$SqlServer  = "localhost"          # ⚠️ AJUSTAR: la instancia donde vive DGL
$Database   = "DGL"
$OutputPath = "$PSScriptRoot\..\csv\seasons_dates.csv"   # ⚠️ AJUSTAR si va a otro lado

# --- La consulta ---------------------------------------------------------------------
# La clave es (season, sports_id). `sports_id` es tinyint y 1 es MLB — hoy es la única liga que el
# sitio usa, pero va en la clave para no tener que migrarla si mañana entra otra.
#
# `season_start_date` y `season_end_date` no pueden venir nulas: una temporada es justamente el
# intervalo entre esas dos. Las otras tres sí pueden faltar — no todos los años tienen registrado el
# Juego de Estrellas, y una temporada en curso todavía no tiene fecha de postemporada.
$Query = @"
SELECT  [season]
       ,[sports_id]
       ,CONVERT(varchar(10), [season_start_date], 23)      AS [season_start_date]
       ,CONVERT(varchar(10), [reg_season_end_date], 23)    AS [reg_season_end_date]
       ,CONVERT(varchar(10), [all_star_game_date], 23)     AS [all_star_game_date]
       ,CONVERT(varchar(10), [post_season_start_date], 23) AS [post_season_start_date]
       ,CONVERT(varchar(10), [season_end_date], 23)        AS [season_end_date]
       ,[is_active]
FROM    [dbo].[v_dglweb_season_dates]
ORDER BY [season];
"@

# --- Ejecución -----------------------------------------------------------------------
# Se usa ADO.NET y no `Invoke-Sqlcmd` a propósito: ese cmdlet vive en el módulo `SqlServer`, que no
# viene instalado por defecto y obligaría a un `Install-Module` antes de poder correr esto. ADO.NET
# es parte de .NET, así que el script funciona en cualquier PowerShell sin preparar nada.
$destino = Split-Path -Parent $OutputPath
if (-not (Test-Path $destino)) { New-Item -ItemType Directory -Path $destino | Out-Null }

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

$tabla | Export-Csv -Path $OutputPath -NoTypeInformation -Encoding UTF8
Write-Host "Escritas $($tabla.Rows.Count) filas en $OutputPath"

# Resumen para revisar antes de subir.
$temporadas = ($tabla | Measure-Object season -Minimum -Maximum)
$activas = @($tabla | Where-Object { $_.is_active -eq $true })
"Total {0} filas | temporadas {1}-{2} | en curso: {3}" -f `
    $tabla.Rows.Count, $temporadas.Minimum, $temporadas.Maximum, `
    $(if ($activas.Count) { ($activas | ForEach-Object { $_.season }) -join ', ' } else { 'ninguna' })

# Los tres avisos que evitan un viaje de ida y vuelta: es mas barato arreglar la vista que subir el
# CSV, esperar la validacion y volver. El import bloquea los tres casos.
$repetidos = $tabla | Group-Object season, sports_id | Where-Object { $_.Count -gt 1 }
if ($repetidos) { Write-Warning "Clave repetida en $($repetidos.Count) caso(s): $($repetidos.Name -join ' | ')" }

if ($activas.Count -gt 1) {
    Write-Warning "Hay $($activas.Count) temporadas marcadas como en curso y solo puede haber una."
}

# Fechas fuera de orden. Se comprueban en el orden en que ocurren; las ausentes se saltan.
$orden = 'season_start_date', 'all_star_game_date', 'reg_season_end_date', 'post_season_start_date', 'season_end_date'
foreach ($fila in $tabla) {
    $previo = $null
    foreach ($campo in $orden) {
        if ($fila.$campo -is [DBNull] -or [string]::IsNullOrWhiteSpace($fila.$campo)) { continue }
        if ($previo -and ($fila.$campo -lt $previo)) {
            Write-Warning "Temporada $($fila.season): $campo ($($fila.$campo)) es anterior a la fecha previa ($previo)."
        }
        $previo = $fila.$campo
    }
}
