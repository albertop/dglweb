# =====================================================================================
# Salarios de dominicanos — export de DGL para el sitio
# =====================================================================================
#
# POR QUÉ EXISTE
# --------------
# El salario no está en la API de MLB, que es de donde sale todo lo demás del sitio. Solo existe en
# DGL, así que entra por esta vía manual: este script lo exporta y el Backoffice lo sube.
#
# EL GRANO
# --------
# Una fila por (jugador, temporada, EQUIPO). El equipo va en la clave a propósito: un pelotero
# traspasado a mitad de año cobra de dos organizaciones, así que su temporada son dos filas y no
# una. Sumarlas da la temporada completa.
#
# Sin `team_id` en la clave, esas dos filas legítimas se verían como un duplicado y el import
# bloquearía la carga entera.
#
# CÓMO SE USA
# -----------
#   1. Correr este script (necesita acceso a DGL en SQL Server).
#   2. Subir el CSV en el Backoffice: Datos de apoyo -> dom_salaries -> Cargar.
#   3. La pantalla compara contra lo que ya está ANTES de escribir nada.
#
# La carga es TRUNCATE: reemplaza la tabla entera y no conserva lo que había.
#
# Ver docs/DATOS_DE_APOYO.md y docs/MOTOR_DATOS_APOYO.md.
# =====================================================================================

# --- Nada de formato regional --------------------------------------------------------
# `Export-Csv` formatea segun la cultura de la maquina, y eso ya causo un problema real con las
# fechas de `dom_players` («7/6/1987»: ambiguo). Aca todas las columnas son enteros, pero la cultura
# invariante va igual: separadores de miles o de decimales segun la maquina romperian el import de
# la misma forma (el salario es la columna en riesgo), y el costo de prevenirlo es una linea.
[System.Threading.Thread]::CurrentThread.CurrentCulture = [System.Globalization.CultureInfo]::InvariantCulture

# --- Configuración -------------------------------------------------------------------
$SqlServer  = "localhost"          # ⚠️ AJUSTAR: la instancia donde vive DGL
$Database   = "DGL"
$OutputPath = "$PSScriptRoot\..\csv\dom_salaries.csv"   # ⚠️ AJUSTAR si va a otro lado

# --- La consulta ---------------------------------------------------------------------
# Seis columnas. `player_id`, `season` y `team_id` son la clave y no pueden faltar; `league_id`,
# `age` y `salary` pueden venir nulos.
#
# Ojo: `team_id` es `char(3)` y `league_id` es `char(2)` — códigos de DGL, y sus valores NO se
# corresponden con nada de la data de MLB. No se intentan traducir al `team`/`league` de las tablas
# del proxy: son dos universos, y casarlos exigiría un mapeo que hoy no existe.
$Query = @"
SELECT  [player_id]
       ,[season]
       ,[team_id]
       ,[league_id]
       ,[age]
       ,[salary]
FROM    [dbo].[v_dglweb_salaries]
ORDER BY [player_id], [season], [team_id];
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

# Un resumen para revisar antes de subir. El total de la nomina es la cifra que mas dice: si cae de
# golpe respecto de la carga anterior, conviene mirar la vista antes de reemplazar la tabla.
$conSalario = $tabla | Where-Object { $_.salary -isnot [DBNull] }
$total = ($conSalario | Measure-Object salary -Sum).Sum
$temporadas = ($tabla | Group-Object season).Count
"Total {0} filas | {1} temporadas | nomina USD {2:N0} | sin salario {3}" -f `
    $tabla.Rows.Count, $temporadas, $total, ($tabla.Rows.Count - $conSalario.Count)

# La clave repetida revienta el import, asi que se avisa aca: es mas barato arreglar la vista que
# subir el CSV, esperar la validacion y volver. Si esto salta, lo mas probable es que la vista tenga
# dos filas del mismo jugador-temporada-equipo que deberian ser una.
$repetidos = $tabla | Group-Object player_id, season, team_id | Where-Object { $_.Count -gt 1 }
if ($repetidos) {
    Write-Warning "Clave repetida en $($repetidos.Count) caso(s): $(($repetidos | Select-Object -First 5).Name -join ' | ')"
}

# Los salarios negativos no existen: si aparecen, es la vista o el export. El import los bloquea.
$negativos = $tabla | Where-Object { $_.salary -isnot [DBNull] -and $_.salary -lt 0 }
if ($negativos) { Write-Warning "Salario negativo en $($negativos.Count) fila(s)." }
