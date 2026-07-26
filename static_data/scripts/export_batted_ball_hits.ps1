# =====================================================================================
# Hits por tipo de batazo — export de DGL (Retrosheet) para el sitio
# =====================================================================================
#
# POR QUÉ EXISTE
# --------------
# A la API de MLB, que es de donde sale todo lo demás del sitio, le faltan los hits por tipo de
# batazo en diez temporadas: 1989-90, 1993-97 y 2000-02. En 2000 y 2001 entrega menos del 2%
# (91 y 113 hits tipificados, contra ~5.000 en los años vecinos), y el efecto se ve en que los
# cuatro coeficientes dejan de sumar 100%: los de Sammy Sosa suman 99.8% en 1999 y 55.9% en 2000.
#
# Retrosheet SÍ los tiene, con ~97% de cobertura en esos mismos años. O sea que el hueco es de
# nuestra fuente, no del registro histórico. Este script los extrae.
#
# Los OUTS por tipo del proxy están completos y no se tocan: acá solo van los hits.
#
# CÓMO SE USA
# -----------
#   1. Correr este script (necesita acceso a DGL en SQL Server).
#   2. Subir el CSV en el Backoffice: Datos de apoyo -> dgl_batted_ball_hits -> Cargar.
#   3. La pantalla compara contra lo que ya está ANTES de escribir nada.
#
# Ver docs/DATOS_DE_APOYO.md y docs/MOTOR_DATOS_APOYO.md.
# =====================================================================================

# --- Configuración -------------------------------------------------------------------
$SqlServer  = "localhost"          # ⚠️ AJUSTAR: la instancia donde vive DGL
$Database   = "DGL"
$OutputPath = "$PSScriptRoot\..\csv\batted_ball_hits.csv"   # ⚠️ AJUSTAR si va a otro lado

# --- La consulta ---------------------------------------------------------------------
# EVENT_CD 20/21/22/23 = sencillo, doble, triple, jonrón.
# BATTEDBALL_CD lleva la trayectoria: G roletazo, F elevado, L línea, P palomita. El jonrón siempre
# la trae (verificado: 0 nulos en cuatro años) y siempre es F o L, así que queda contado dentro de
# los elevados — igual que en nuestra columna `fly_hits`, que también incluye HR.
#
# Se emiten DOS bloques: los hits que CONECTÓ el jugador (BAT_ID -> batting) y los que le
# PERMITIERON como lanzador (PIT_ID -> pitching). Los dos oficios tienen el mismo hueco, medido.
#
# Se identifica al jugador por `mlbID`, que es la misma llave con la que trabaja el sitio: así el CSV
# llega listo para casar con `dgl_master` sin pasar por el retroID. El join contra retroEventsReg sí
# usa retroID, que es la llave de Retrosheet.
#
# SOLO 1989-2002, que es donde nuestra fuente tiene el hueco:
#   * Antes del 89 la clasificación de Retrosheet tampoco está completa, y 1989 es además el piso que
#     ya usa el motor de líderes (`derive.FIRST_STATCAST_SEASON`).
#   * Después de 2002 la API de MLB tipifica el 100% y Retrosheet ~97,5%, así que traerlo sería
#     cambiar dato bueno por dato peor. Pasó en la primera carga real, cuando el script exportaba
#     todo el rango: las temporadas 2004-2019 bajaron de 99-100% a ~97%.
#
# El loader tiene además una guarda que solo pisa al proxy cuando el entrante tipifica más, así que
# aunque este rango se amplíe por error no se degrada nada. Son dos defensas para el mismo fallo,
# a propósito: el rango evita traer lo que no hace falta, la guarda evita el daño si igual llega.
#
# `h_typed` es el total de hits CON trayectoria y `h_all` el total de hits del jugador. No son
# iguales: a Retrosheet le falta la trayectoria en ~2,5% de los hits (126 filas en 2000, 115 en
# 2001, 0 en 1999). Se exportan los dos para que la validación del import pueda decidir contra
# cuál compara — ver la nota al pie de este archivo.
$Query = @"
WITH eventos AS (
    SELECT  m.mlbID                AS mlb_id,
            e.SEASON               AS season,
            'batting'              AS stat_group,
            e.BATTEDBALL_CD        AS bb
    FROM    dbo.retroEventsReg e
            INNER JOIN dbo.dglMaster m ON e.BAT_ID = m.retroID
    WHERE   e.EVENT_CD IN (20, 21, 22, 23)
      AND   e.SEASON BETWEEN 1989 AND 2002

    UNION ALL

    SELECT  m.mlbID                AS mlb_id,
            e.SEASON               AS season,
            'pitching'             AS stat_group,
            e.BATTEDBALL_CD        AS bb
    FROM    dbo.retroEventsReg e
            INNER JOIN dbo.dglMaster m ON e.PIT_ID = m.retroID
    WHERE   e.EVENT_CD IN (20, 21, 22, 23)
      AND   e.SEASON BETWEEN 1989 AND 2002
)
SELECT  mlb_id,
        season,
        stat_group,
        SUM(CASE WHEN bb = 'G' THEN 1 ELSE 0 END) AS ground_hits,
        SUM(CASE WHEN bb = 'F' THEN 1 ELSE 0 END) AS fly_hits,
        SUM(CASE WHEN bb = 'L' THEN 1 ELSE 0 END) AS line_hits,
        SUM(CASE WHEN bb = 'P' THEN 1 ELSE 0 END) AS pop_hits,
        SUM(CASE WHEN bb IN ('G','F','L','P') THEN 1 ELSE 0 END) AS h_typed,
        COUNT(*)                                                 AS h_all
FROM    eventos
GROUP BY mlb_id, season, stat_group
ORDER BY mlb_id, season, stat_group;
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
    $cmd.CommandTimeout = 300          # la tabla de eventos es grande; 5 minutos de margen
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

# Un resumen por temporada para revisar de un vistazo antes de subir el CSV.
$tabla | Group-Object season | Sort-Object Name | ForEach-Object {
    $tip = ($_.Group | Measure-Object h_typed -Sum).Sum
    $all = ($_.Group | Measure-Object h_all   -Sum).Sum
    $pct = if ($all) { 100 * $tip / $all } else { 0 }
    "{0}  {1,6} hits  {2,5:N1}% con trayectoria" -f $_.Name, $all, $pct
}

# =====================================================================================
# NOTA PENDIENTE — la prueba de aceptación
# =====================================================================================
# El import valida que los cuatro tipos sumen H. Con este CSV eso NO va a dar exacto, por dos
# razones que no son errores:
#
#   1. A Retrosheet le falta la trayectoria en ~2,5% de los hits. Esos quedan fuera de los cuatro
#      conteos pero dentro de `h_all`.
#   2. Nuestro maestro de dominicanos es ~10% más amplio que el join con dglMaster, así que el
#      total de Retrosheet no coincide con el H que ya tenemos del proxy.
#
# Por eso se exportan `h_typed` y `h_all`: hay que decidir contra cuál compara el loader, y con
# qué tolerancia. Ver docs/DATOS_DE_APOYO.md, sección "Decisiones abiertas".
# =====================================================================================
