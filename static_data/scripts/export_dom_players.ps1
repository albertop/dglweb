# =====================================================================================
# Dominicanos en el sistema profesional — export de DGL para el sitio
# =====================================================================================
#
# QUÉ ES ESTA TABLA
# -----------------
# `dom_players` es más ancha que `dgl_master`. El maestro son los dominicanos que SÍ llegaron a
# Grandes Ligas, y es la autoridad del sitio: quien está ahí es un pelotero de las mayores. Esta
# otra incluye a los que todavía no debutaron, y sirve para ver quién viene subiendo — detectar
# debuts y movimientos de roster.
#
# Por eso sale de `v_dglweb_master_no_debuts`, que es justamente la vista sin el filtro de debut.
#
# EL FILTRO DE EDAD
# -----------------
# Solo los nacidos en los últimos 40 años. Un dominicano de más de 40 que todavía no debutó ya no
# va a debutar, así que ocupa lugar sin aportar. La tabla pasa de ~11.700 filas a ~9.600.
#
# Ojo con el criterio: `year(getdate()) - year(birth_date)` no es la edad exacta —quien cumple 40 en
# diciembre ya cuenta como 40 desde enero— así que en la práctica el corte es "nacidos en los últimos
# 40 años calendario". Para lo que sirve la tabla da lo mismo, pero conviene saber qué dice.
#
# Los que NO tienen fecha de nacimiento se incluyen a propósito (`or birth_date is null`). Sin esa
# cláusula el `year(NULL)` los dejaba fuera en silencio, y desaparecer sin que nada lo diga es
# exactamente lo que no queremos: si a un prospecto le falta la fecha, el problema es la fecha, no
# el prospecto.
#
# CÓMO SE USA
# -----------
#   1. Correr este script (necesita acceso a DGL en SQL Server).
#   2. Subir el CSV en el Backoffice: Datos de apoyo -> dom_players -> Cargar.
#   3. La pantalla compara contra lo que ya está ANTES de escribir nada.
#
# La carga es TRUNCATE: reemplaza la tabla entera y no conserva lo que había. Es deliberado — el
# contenido viejo de esta tabla no se reconcilia, se sustituye.
#
# Ver docs/DATOS_DE_APOYO.md y docs/MOTOR_DATOS_APOYO.md.
# =====================================================================================

# --- Nada de formato regional --------------------------------------------------------
# `Export-Csv` formatea segun la cultura de la maquina: en una es escribe «7/6/1987» y en otra
# «6/7/1987», y las dos son la misma fecha con distinto significado. Ninguna columna de este export
# debe depender de donde se corrio el script, asi que:
#   1. La fecha se convierte a ISO EN SQL (estilo 23), abajo en la consulta. Esa es la defensa real.
#   2. Y ademas se fija cultura invariante en el hilo, por si manana se suma una columna con formato.
[System.Threading.Thread]::CurrentThread.CurrentCulture = [System.Globalization.CultureInfo]::InvariantCulture

# --- Configuración -------------------------------------------------------------------
$SqlServer  = "localhost"          # ⚠️ AJUSTAR: la instancia donde vive DGL
$Database   = "DGL"
$OutputPath = "$PSScriptRoot\..\csv\dom_players.csv"   # ⚠️ AJUSTAR si va a otro lado

# --- La consulta ---------------------------------------------------------------------
# Trece columnas: las que el sitio usa. La vista trae más, pero cargar lo que no se usa solo agrega
# columnas que hay que mantener sincronizadas entre SQL Server, el CSV y Postgres.
#
# `player_id` es el ID de MLB y es la clave: el import exige que venga y que no se repita. El resto
# es descriptivo y puede faltar — un prospecto recién cargado casi no tiene datos.
#
# ⚠️ La fecha se convierte a ISO EN SQL (estilo 23 = yyyy-mm-dd) y no se deja salir como `datetime`.
# `Export-Csv` la escribiría con el formato regional de la máquina, y «7/6/1987» es ambiguo: 7 de
# junio o 6 de julio según quién corrió el script. El import rechaza cualquier cosa que no sea ISO
# justamente para que esa ambigüedad no entre nunca a la base.
$Query = @"
SELECT  [player_id]
       ,[last_name]
       ,[first_name]
       ,[full_name]
       ,CONVERT(varchar(10), [birth_date], 23) AS [birth_date]   -- ISO yyyy-mm-dd, siempre
       ,[birth_place]
       ,[bats]
       ,[throws]
       ,[height]
       ,[weight]
       ,[is_active]
       ,[is_player]
       ,[is_verified]
FROM    [dbo].[v_dglweb_master_no_debuts]
WHERE   (YEAR(GETDATE()) - YEAR(birth_date) < 40) OR birth_date IS NULL
ORDER BY [player_id];
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

# Un resumen para revisar de un vistazo antes de subir el CSV. Si el total cae de golpe respecto de
# la carga anterior, conviene mirar la vista antes de reemplazar la tabla — el import va a mostrar
# la comparación igual, pero es mejor enterarse acá.
$sinFecha = ($tabla | Where-Object { $_.birth_date -is [DBNull] }).Count
$activos  = ($tabla | Where-Object { $_.is_active -eq $true }).Count
"Total {0} | activos {1} | sin fecha de nacimiento {2}" -f $tabla.Rows.Count, $activos, $sinFecha

# Los ids repetidos revientan el import, así que se avisa acá — es más barato arreglar la vista que
# subir el CSV, esperar la validación y volver.
$repetidos = $tabla | Group-Object player_id | Where-Object { $_.Count -gt 1 }
if ($repetidos) {
    Write-Warning "player_id repetido en $($repetidos.Count) caso(s): $($repetidos.Name -join ', ')"
}
