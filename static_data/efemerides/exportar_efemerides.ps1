# =====================================================================================
# Efemérides dominicanas — el motor
# =====================================================================================
#
# QUÉ HACE
# --------
# Recorre `detectores/*.sql`, corre cada uno contra DGL, valida que devuelvan el contrato, une todo,
# puntúa, fusiona los duplicados y escribe un CSV que el Backoffice sube a `dgl_efemerides`.
#
# ESTE ARCHIVO NO SE TOCA AL AGREGAR UNA EFEMÉRIDE. Agregar una es escribir un `.sql` más en
# `detectores/`. Si para meter un detector hay que venir acá, el diseño se rompió — ver
# docs/EFEMERIDES.md sección 8.
#
# CÓMO SE USA
# -----------
#   1. Correr este script, una vez al año, después de que Retrosheet publique.
#   2. Subir el CSV en el Backoffice: Datos de apoyo -> dgl_efemerides -> Cargar.
#   3. La pantalla compara contra lo que ya está ANTES de escribir nada, así que enseña
#      exactamente lo que agregó la temporada nueva.
#
# El diseño completo, con el porqué de cada número, está en docs/EFEMERIDES.md.
# =====================================================================================

[System.Threading.Thread]::CurrentThread.CurrentCulture = [System.Globalization.CultureInfo]::InvariantCulture

$SqlServer  = "localhost"          # ⚠️ AJUSTAR: la instancia donde vive DGL
$Database   = "DGL"
$OutputPath = "$PSScriptRoot\..\csv\dgl_efemerides.csv"

# --- El contrato ---------------------------------------------------------------------
# Las columnas que TODO detector debe devolver. Se valida antes de usar nada: un detector al que le
# falte una columna aborta la corrida entera en vez de colar filas mutiladas que nadie va a mirar
# hasta que salgan mal en la página.
$CONTRATO = @(
    'tipo', 'rol', 'cobertura', 'universo', 'plantilla', 'situar',
    'mlb_id', 'nombre', 'fecha', 'temporada', 'game_id', 'event_id', 'game_type',
    'equipo', 'rival', 'en_casa', 'signo', 'magnitud', 'wpa_jugador', 'li_max', 'detalle',
    'equipo_nombre', 'rival_nombre', 'oponente'
)

# `situar` (1/0) dice si la frase «uno de los N dominicanos que lo ha logrado» tiene sentido para
# esa gesta. Lo declara el detector porque es lo único que él sabe: para un ciclo la frase es el
# alma de la efeméride, para un cumpleaños es un disparate — todo el mundo cumple años.
#
# Salió de la primera corrida del motor, que publicó dos frases absurdas: «Cumple 51 años. Fue el
# primer dominicano en lograrlo» y «Cumple 46 años. Es uno de los 923 dominicanos que lo ha
# logrado». Y no era solo el texto: el bono de relieve le daba +30 a Fernando Tatís por haber
# nacido un 1 de enero —el primero del año, o sea el primero de la lista— y con eso superaba a
# Albert Pujols, que tiene tres veces más juegos en su carrera.
#
# No se decide por `rol` porque no es lo mismo: `debut` también es `rol = persona` y ahí la frase
# SÍ vale — «el primer dominicano en llegar a Grandes Ligas» es de las mejores efemérides que hay.

# --- Los topes del puntaje ------------------------------------------------------------
# Las ÚNICAS constantes puestas a mano en todo el sistema. Todo lo demás sale de los datos.
# Ver docs/EFEMERIDES.md sección 4.
$TOPE_RAREZA    = 600    # y 300 para los hechos negativos — ver 4.5
$TOPE_MAGNITUD  = 200
$TOPE_IMPACTO   = 150
$TOPE_RELIEVE   = 50

# El WPA a partir del cual el bono de impacto satura. 0,5 es «prácticamente ganó el juego él solo»:
# medido, el mejor escape de bases llenas de la historia dominicana está en 0,89 y los walk-off
# grandes rondan 0,6-0,7. Por encima de 0,5 la diferencia ya no distingue nada útil.
$WPA_SATURA = 0.5

# =====================================================================================
# Ayudantes
# =====================================================================================

function Get-Conexion {
    $cs = "Server=$SqlServer;Database=$Database;Integrated Security=True;TrustServerCertificate=True"
    $cn = New-Object System.Data.SqlClient.SqlConnection $cs
    $cn.Open()
    return $cn
}

function Invoke-Detector {
    <#
        Corre un .sql y devuelve sus filas como objetos, validando el contrato.

        El timeout es alto a propósito: los detectores de evento barren 16 millones de filas y esto
        corre una vez al año. Que tarde no importa; que se corte a la mitad, sí.
    #>
    param([System.Data.SqlClient.SqlConnection] $Conexion, [System.IO.FileInfo] $Archivo)

    $cmd = $Conexion.CreateCommand()
    $cmd.CommandText    = [System.IO.File]::ReadAllText($Archivo.FullName)
    $cmd.CommandTimeout = 3600

    $tabla = New-Object System.Data.DataTable
    $tabla.Load($cmd.ExecuteReader())

    $columnas = $tabla.Columns | ForEach-Object { $_.ColumnName }
    $faltan   = $CONTRATO | Where-Object { $_ -notin $columnas }
    if ($faltan) {
        throw "$($Archivo.Name): le faltan columnas del contrato -> $($faltan -join ', ')"
    }

    # Las de más no rompen nada, pero casi siempre son una columna mal nombrada. Se avisa.
    $sobran = $columnas | Where-Object { $_ -notin $CONTRATO }
    if ($sobran) {
        Write-Warning "$($Archivo.Name): devuelve columnas que no son del contrato -> $($sobran -join ', ')"
    }

    return @($tabla.Rows | ForEach-Object { $fila = $_; $o = [ordered]@{}; foreach ($c in $CONTRATO) { $o[$c] = $fila[$c] }; [pscustomobject]$o })
}

function Get-Rareza {
    <#
        600 × (1 − log(n) / log(N)), o 300 si el hecho es negativo.

        `n` es cuántas veces ocurrió la gesta y `N` el universo de oportunidades del MISMO GRANO —
        que lo declara el detector, porque solo él sabe si su unidad es un juego, un turno o una
        entrada. Ver docs/EFEMERIDES.md 5.2.11.
    #>
    param([int] $Veces, [double] $Universo, [int] $Signo)

    if ($Veces -le 0 -or $Universo -le 1) { return 0.0 }
    $tope = if ($Signo -lt 0) { 300.0 } else { [double]$TOPE_RAREZA }
    # Con n=1 el logaritmo es 0 y la rareza satura en el tope. Es correcto: pasó una sola vez.
    return $tope * (1.0 - ([Math]::Log10([double]$Veces) / [Math]::Log10($Universo)))
}

function Get-Magnitud {
    <#
        Dónde cae esta magnitud dentro de la distribución de su propio tipo, de 0 a 200.

        Percentil y no una escala absoluta porque cada tipo mide otra cosa: 4 jonrones, 15 ponches y
        0,87 de WPA no se comparan entre sí, pero sí contra los suyos.
    #>
    param([double] $Valor, [double[]] $Todas, [int] $Signo)

    # Los negativos corren a MEDIA ESCALA también acá, no solo en la rareza. La primera versión solo
    # partía la rareza, y el resultado se vio al correr 33 detectores: `cs3` —atrapado robando tres
    # veces, una sola vez en la historia— sacaba 550 y empataba con un juego de TRES JONRONES (552).
    # Una deshonra no puede valer lo que una hazaña por el mero hecho de ser rara.
    $tope = if ($Signo -lt 0) { [double]$TOPE_MAGNITUD / 2 } else { [double]$TOPE_MAGNITUD }

    if ($Todas.Count -le 1) { return $tope }
    $menores = @($Todas | Where-Object { $_ -lt $Valor }).Count
    return $tope * ($menores / [double]($Todas.Count - 1))
}

function Get-Impacto {
    <#
        Cuánto movió el juego, de 0 a 150, a partir del WPA.

        NO APLICA A LOS NEGATIVOS: usar el valor absoluto premiaría la mala noche, que es
        exactamente al revés. Ver docs/EFEMERIDES.md 4.5.
    #>
    param($Wpa, [int] $Signo)

    if ($Signo -lt 0) { return 0.0 }
    if ($null -eq $Wpa -or $Wpa -is [DBNull]) { return 0.0 }
    $w = [Math]::Max(0.0, [double]$Wpa)
    return $TOPE_IMPACTO * [Math]::Min(1.0, $w / $WPA_SATURA)
}

function Get-Relieve {
    <#
        El bono de «primero» y «único», de 0 a 50.

        Lee los mismos campos que el texto (3.3), así que el puntaje y la frase no pueden
        contradecirse: si la efeméride dice «el primero», el puntaje lo refleja.

        Con cobertura parcial NO se da: no sabemos si fue el primero, solo que es el primero que
        vemos. Ver 5.2.5.
    #>
    param([int] $Orden, [int] $VecesTotal, [bool] $Completa, [int] $Situar, [int] $Signo)

    # A UNA DESHONRA NO SE LE DA EL BONO DE «EL ÚNICO». Ser el único que falló así no es un honor, y
    # premiarlo era lo que ponía `cs3` a la altura de un juego de tres jonrones.
    if ($Signo -lt 0) { return 0.0 }

    # Sin `situar` no hay «primero» que premiar: el primero de una lista de cumpleaños es solo el
    # que nació más temprano en el año.
    if ($Situar -eq 0) { return 0.0 }
    if (-not $Completa) { return 0.0 }
    if ($VecesTotal -eq 1) { return [double]$TOPE_RELIEVE }        # el único
    if ($Orden -eq 1)      { return $TOPE_RELIEVE * 0.6 }          # el primero
    return 0.0
}

function Get-Situacion {
    <#
        La frase que sitúa la efeméride: «uno de los 34 dominicanos que lo ha logrado».

        Es lo que el dueño pidió y lo que convierte un dato en noticia — sin denominador, el lector
        no sabe si vio algo raro o algo de todos los días.

        CON COBERTURA PARCIAL DEVUELVE VACÍO. El número que tenemos es el de la ventana que vemos, no
        el de la historia, y publicarlo como total sería mentir con precisión decimal.
    #>
    param([int] $Orden, [int] $VecesTotal, [int] $JugadoresTotal, [int] $VecesJugador,
          [int] $OrdenJugador, [bool] $Completa, [int] $Situar, [int] $Signo)

    if ($Situar -eq 0)  { return "" }
    if (-not $Completa) { return "" }

    # `situar = 2` — SOLO SI ES EL PRIMERO O EL ÚNICO.
    #
    # Es para las gestas que TODOS hicieron. El debut es el caso: los 984 del maestro debutaron, así
    # que «Es uno de los 984 dominicanos que lo ha logrado» no dice nada. Pero «Fue el primer
    # dominicano en llegar a Grandes Ligas» es de las mejores efemérides que hay, y se perdería si el
    # detector se apagara del todo con `situar = 0`.
    if ($Situar -eq 2 -and $Orden -ne 1 -and $VecesTotal -ne 1) { return "" }

    # EL VERBO CAMBIA CON EL SIGNO. La primera versión decía «lo ha logrado» para todo, y la muestra
    # de redacción la dejó en evidencia: «Bateó para 3 dobles matanzas… Fue el primer dominicano en
    # LOGRARLO» y «Lo atraparon robando 3 veces… Es el único dominicano que lo ha LOGRADO». Nadie
    # logra un ponche. A una deshonra le pasa.
    if ($Signo -lt 0) {
        if ($VecesTotal -eq 1) { return "Es el único dominicano al que le ha pasado." }
        if ($Orden -eq 1)      { return "Fue el primer dominicano al que le pasó." }
        $frase = "Le ha pasado a $JugadoresTotal dominicanos."
        if ($VecesJugador -gt 1) { $frase += " A él le pasó $VecesJugador veces." }
        return $frase
    }

    if ($VecesTotal -eq 1)  { return "Es el único dominicano que lo ha logrado." }
    if ($Orden -eq 1)       { return "Fue el primer dominicano en lograrlo." }

    $frase = if ($JugadoresTotal -eq 1) {
        "Es el único dominicano que lo ha logrado, y van $VecesTotal veces."
    } else {
        "Es uno de los $JugadoresTotal dominicanos que lo ha logrado."
    }
    # «Para él, la número 5» era TRIPLEMENTE ambiguo, y lo cazó el dueño leyendo la muestra:
    #
    #   * salía de `veces_jugador` —su TOTAL— pero se leía como «esta fue su quinta»;
    #   * si el juego era el 3.º de sus 5, el número no correspondía a nada;
    #   * y encima se entendía como «fue el quinto dominicano en lograrlo», que es `orden`.
    #
    # Con los DOS números no queda margen: cuál de las suyas fue, y de cuántas.
    if ($VecesJugador -gt 1) { $frase += " Para él fue la $($OrdenJugador)ª de sus $VecesJugador." }
    return $frase
}

function Expand-Plantilla {
    <#
        Rellena `{campo}` con el valor de la fila.

        LA PLANTILLA LA DECLARA EL DETECTOR, como una constante de su SELECT. Así el texto vive en el
        mismo archivo que la consulta que lo alimenta —se lee entero de un vistazo— y agregar una
        efeméride sigue siendo tocar UN archivo. El detector no «escribe texto»: declara la forma; el
        motor la rellena con lo que el detector no puede saber.
    #>
    param([string] $Plantilla, [pscustomobject] $Fila)

    $texto = $Plantilla
    foreach ($p in $Fila.PSObject.Properties) {
        $valor = if ($null -eq $p.Value -or $p.Value -is [DBNull]) { "" } else { [string]$p.Value }
        $texto = $texto.Replace("{$($p.Name)}", $valor)
    }
    return $texto
}

# =====================================================================================
# 1. Correr los detectores
# =====================================================================================

$carpeta = Join-Path $PSScriptRoot 'detectores'
if (-not (Test-Path $carpeta)) { Write-Error "No existe $carpeta"; exit 1 }

$todos = @(Get-ChildItem -Path $carpeta -Filter '*.sql' | Sort-Object Name)

# LOS QUE EMPIEZAN POR `_` SON PRELUDIOS, NO DETECTORES. Dejan tablas temporales puestas —los
# nombres de equipos y de peloteros, los abridores— y no devuelven efemérides, así que no se les
# exige el contrato ni se recogen sus filas. Corren primero por el orden alfabético del guion bajo, y
# sobreviven al resto porque toda la corrida usa UNA sola conexión.
$preludios = @($todos | Where-Object { $_.Name.StartsWith('_') })
$archivos  = @($todos | Where-Object { -not $_.Name.StartsWith('_') })
if ($archivos.Count -eq 0) { Write-Error "No hay detectores en $carpeta"; exit 1 }

Write-Host "Preludios: $($preludios.Count)   Detectores: $($archivos.Count)"
$hechos = [System.Collections.Generic.List[object]]::new()

try {
    $cn = Get-Conexion

    foreach ($p in $preludios) {
        $t0 = Get-Date
        $cmd = $cn.CreateCommand()
        $cmd.CommandText    = [System.IO.File]::ReadAllText($p.FullName)
        $cmd.CommandTimeout = 3600
        [void]$cmd.ExecuteNonQuery()
        "  {0,-34} {1,6}       {2,4}s" -f $p.Name, '(preludio)', [int]((Get-Date) - $t0).TotalSeconds | Write-Host
    }

    foreach ($a in $archivos) {
        $t0 = Get-Date
        $filas = Invoke-Detector -Conexion $cn -Archivo $a
        $seg = [int]((Get-Date) - $t0).TotalSeconds
        "  {0,-34} {1,6} filas  {2,4}s" -f $a.Name, $filas.Count, $seg | Write-Host
        foreach ($f in $filas) { $hechos.Add($f) }
    }
}
catch {
    Write-Error "Falló un detector: $_"
    exit 1
}
finally {
    if ($cn -and $cn.State -eq 'Open') { $cn.Close() }
}

if ($hechos.Count -eq 0) { Write-Error "Ningun detector devolvio filas."; exit 1 }

# --- La comprobación del maestro ------------------------------------------------------
# En una corrida normal esto es 0: el debutante se inscribe en `dglMaster` DESPUÉS de debutar y este
# script corre DESPUÉS de que Retrosheet publica, así que a esa altura todos tienen `retroID`. Si no
# es 0, algo pasó —Retrosheet no cubrió a alguien, o se inscribió a quien no ha debutado— y hay que
# mirarlo antes de subir el CSV. Ver docs/EFEMERIDES.md 10.1.
try {
    $cn2 = Get-Conexion
    $c = $cn2.CreateCommand()
    $c.CommandText = "SELECT COUNT(1) FROM dglMaster WHERE retroID IS NULL OR retroID = ''"
    $sinRetro = [int]$c.ExecuteScalar()
    if ($sinRetro -gt 0) {
        Write-Warning "$sinRetro fila(s) de dglMaster sin retroID. En una corrida normal esto es 0 — revisar antes de subir."
    }
}
finally { if ($cn2 -and $cn2.State -eq 'Open') { $cn2.Close() } }

# =====================================================================================
# 2. Los conteos, por tipo — lo que el detector no puede saber
# =====================================================================================
#
# SE AGRUPA POR `mlb_id`, NUNCA POR NOMBRE. `nameList` no es único: hay tres Luis Castillo, dos
# Nelson Cruz y dos José Ramírez en el maestro, así que contar por nombre daría un número menor que
# el real y menor sin avisar. Ver docs/EFEMERIDES.md 3.0.1.

Write-Host "Puntuando..."

foreach ($grupo in ($hechos | Group-Object tipo)) {
    $delTipo = @($grupo.Group | Sort-Object fecha, game_id, event_id)
    $veces   = $delTipo.Count
    $jugadores = @($delTipo | Group-Object mlb_id).Count
    $universo  = [double]$delTipo[0].universo
    $signo     = [int]$delTipo[0].signo
    $completa  = ([string]$delTipo[0].cobertura) -eq 'completa'
    $situar    = [int]$delTipo[0].situar
    $rareza    = Get-Rareza -Veces $veces -Universo $universo -Signo $signo

    $magnitudes = @($delTipo | ForEach-Object { [double]$_.magnitud })
    $porJugador = @{}

    $i = 0
    foreach ($f in $delTipo) {
        $i++
        $id = [string]$f.mlb_id
        if (-not $porJugador.ContainsKey($id)) { $porJugador[$id] = 0 }
        $porJugador[$id]++

        $f | Add-Member -NotePropertyName veces_total     -NotePropertyValue $veces
        $f | Add-Member -NotePropertyName jugadores_total -NotePropertyValue $jugadores
        $f | Add-Member -NotePropertyName orden           -NotePropertyValue $i
        $f | Add-Member -NotePropertyName orden_jugador   -NotePropertyValue $porJugador[$id]
        $f | Add-Member -NotePropertyName rareza          -NotePropertyValue ([Math]::Round($rareza, 1))
    }

    # `veces_jugador` es el total de cada uno y solo se sabe al terminar de recorrer el tipo.
    foreach ($f in $delTipo) {
        $f | Add-Member -NotePropertyName veces_jugador -NotePropertyValue $porJugador[[string]$f.mlb_id]

        $mag  = Get-Magnitud -Valor ([double]$f.magnitud) -Todas $magnitudes -Signo $signo
        $imp  = Get-Impacto  -Wpa $f.wpa_jugador -Signo $signo
        $rel  = Get-Relieve  -Orden $f.orden -VecesTotal $veces -Completa $completa -Situar $situar -Signo $signo
        $tot  = $f.rareza + $mag + $imp + $rel

        $f | Add-Member -NotePropertyName puntaje -NotePropertyValue ([int][Math]::Round($tot))

        # Con cobertura parcial los totales van VACÍOS, no en cero: cero es un dato y esto es una
        # ausencia. El sitio tiene que poder distinguirlas.
        if (-not $completa) {
            $f.veces_total     = $null
            $f.jugadores_total = $null
        }

        $fecha = [datetime]$f.fecha
        $f | Add-Member -NotePropertyName mes  -NotePropertyValue $fecha.Month
        $f | Add-Member -NotePropertyName dia  -NotePropertyValue $fecha.Day
        $f | Add-Member -NotePropertyName anos -NotePropertyValue ((Get-Date).Year - $fecha.Year)

        $situacion = Get-Situacion -Orden $f.orden -VecesTotal $veces -JugadoresTotal $jugadores `
                                   -VecesJugador $f.veces_jugador -OrdenJugador $f.orden_jugador -Completa $completa -Situar $situar -Signo $signo
        $titular = Expand-Plantilla -Plantilla ([string]$f.plantilla) -Fila $f
        $f | Add-Member -NotePropertyName titular -NotePropertyValue $titular
        $f | Add-Member -NotePropertyName situacion -NotePropertyValue $situacion
    }
}

# =====================================================================================
# 3. La fusión — un batazo, una efeméride
# =====================================================================================
#
# Un walk-off de grand slam dispara tres detectores sobre el MISMO turno. Sin esta regla, el 23 de
# abril de 1999 aparecería el batazo de Tatís repetido. Se queda el de mayor puntaje y los demás se
# anexan como etiquetas. Ver docs/EFEMERIDES.md sección 7.

$antes = $hechos.Count
$fusionados = [System.Collections.Generic.List[object]]::new()

# LA FECHA VA EN LA CLAVE, y no es redundante aunque lo parezca.
#
# La regla del diseño era «mismo jugador + mismo juego + mismo evento», que basta para las gestas de
# juego porque ahí el `game_id` ya implica la fecha. Pero las gestas de PERSONA no cuelgan de ningún
# juego: cumpleaños, debut y fallecimiento del mismo jugador llevan todos `game_id = ''` y
# `event_id = 0`, así que colisionaban entre sí y la fusión se quedaba con una sola.
#
# El síntoma fue exacto: `91_debut.sql` devolvía 984 filas y el archivo terminaba con CERO debuts,
# porque cada uno se fusionaba con el cumpleaños del mismo jugador. Lo destapó la muestra de
# redacción, no una comprobación — el conteo por tipo lo enseñaba y nadie lo estaba leyendo.
foreach ($g in ($hechos | Group-Object { "$($_.mlb_id)|$($_.game_id)|$($_.event_id)|$($_.fecha)" })) {
    # MANDA LA RAREZA, NO EL PUNTAJE, y esto se corrigió después de verlo fallar.
    #
    # La regla era «se queda el de mayor puntaje». Con 46 detectores corriendo salió el problema: un
    # WALK-OFF DE GRAND SLAM aparecía etiquetado como simple «walk-off de jonrón». Los dos disparan
    # sobre el mismo turno, y aunque la rareza del slam es 468 contra 355, el jonrón ganaba por
    # puntaje total — el slam quedaba en percentil bajo dentro de sus 20 hermanos mientras el jonrón
    # quedaba alto dentro de sus 262.
    #
    # Siete de los veinte walk-off de grand slam se estaban perdiendo así.
    #
    # La rareza es lo que codifica QUÉ TAN ESPECÍFICO es el hecho, y un hecho más específico nunca
    # debe perder contra uno que lo contiene. El puntaje solo desempata.
    $ordenados = @($g.Group | Sort-Object -Property @{Expression='rareza'; Descending=$true},
                                                    @{Expression='puntaje'; Descending=$true})
    $principal = $ordenados[0]
    $etiquetas = @($ordenados | Select-Object -Skip 1 | ForEach-Object { $_.tipo })
    $principal | Add-Member -NotePropertyName etiquetas -NotePropertyValue ($etiquetas -join ' ')
    $fusionados.Add($principal)
}

Write-Host "Fusion: $antes hechos -> $($fusionados.Count) efemerides"

# =====================================================================================
# 4. El CSV
# =====================================================================================

# `fecha` se formatea A MANO como ISO. `Export-Csv` la sacaba como «06/28/2023 00:00:00» —formato de
# EE. UU. y con hora— aunque la cultura del hilo esté en invariante, porque lo que exporta es un
# `DateTime` y ese es su `ToString()` por defecto. Es la misma trampa que ya mordió a `dom_players`
# con «7/6/1987», anotada en su exportador: una fecha ambigua rompe el import sin decir por qué.
$fechaISO = @{ Name = 'fecha'; Expression = { ([datetime]$_.fecha).ToString('yyyy-MM-dd') } }

$columnas = @(
    'tipo', 'etiquetas', 'rol', 'signo', 'cobertura',
    'mlb_id', 'nombre', $fechaISO, 'mes', 'dia', 'temporada', 'anos',
    'game_id', 'event_id', 'game_type', 'equipo', 'equipo_nombre', 'rival', 'rival_nombre', 'en_casa', 'oponente',
    'magnitud', 'wpa_jugador', 'li_max', 'detalle',
    'veces_total', 'jugadores_total', 'orden', 'veces_jugador', 'orden_jugador',
    'rareza', 'puntaje', 'titular', 'situacion'
)

$destino = Split-Path -Parent $OutputPath
if (-not (Test-Path $destino)) { New-Item -ItemType Directory -Path $destino | Out-Null }

# EL ORDEN DEL ARCHIVO, que es el orden en que la página va a pintar (decisión del dueño):
#
#   1. mes y día        — el archivo se consulta por «un día como hoy»
#   2. puntaje, de mayor a menor — dentro del día manda la importancia
#   3. fecha, de la más vieja a la más nueva — el desempate
#
# El tercer nivel existe porque el segundo empata a menudo: dos gestas del MISMO tipo en el mismo
# día del calendario —dos juegos de 6 hits un 15 de abril, de años distintos— sacan casi el mismo
# puntaje, y sin desempate el orden lo decidiría el azar del `Group-Object`. Con la fecha, sale
# cronológico y estable: la misma entrada da siempre el mismo archivo, que es lo que hace que la
# pantalla de comparación del Backoffice enseñe solo lo que de verdad cambió.
$fusionados |
    Sort-Object mes, dia, @{Expression = 'puntaje'; Descending = $true}, @{Expression = { [datetime]$_.fecha } } |
    Select-Object $columnas |
    Export-Csv -Path $OutputPath -NoTypeInformation -Encoding UTF8

Write-Host "Escritas $($fusionados.Count) filas en $OutputPath"

# =====================================================================================
# 5. El resumen — para mirar ANTES de subir
# =====================================================================================

$dias = @($fusionados | Group-Object { "{0:00}-{1:00}" -f $_.mes, $_.dia }).Count
$positivas = @($fusionados | Where-Object { [int]$_.signo -gt 0 }).Count

"" | Write-Host
"Efemerides {0} | dias del calendario {1}/366 | positivas {2} | negativas {3}" -f `
    $fusionados.Count, $dias, $positivas, ($fusionados.Count - $positivas) | Write-Host

"`nPor tipo:" | Write-Host
$fusionados | Group-Object tipo | Sort-Object Count -Descending | ForEach-Object {
    "  {0,-22} {1,5}  puntaje max {2}" -f $_.Name, $_.Count, (($_.Group | Measure-Object puntaje -Maximum).Maximum
) | Write-Host }

# =====================================================================================
# UNA LÍNEA DE MUESTRA POR DETECTOR — para validar la redacción
# =====================================================================================
#
# Pedido del dueño: antes de dar un detector por bueno hay que LEER cómo queda su frase. Un umbral
# se valida midiendo, pero una redacción solo se valida leyéndola — la concordancia de «1 empujadas»
# y el «Cumple 46 años. Es uno de los 923 dominicanos que lo ha logrado» no los cazó ninguna medición.
#
# Se muestra la de MAYOR PUNTAJE de cada tipo, que es la que más se va a ver en la página, con su
# frase de situación pegada. Los tipos que hoy devuelven cero salen igual, marcados: un detector
# vacío es una decisión, no un olvido.

"`n" + ("=" * 100) | Write-Host
"MUESTRA DE REDACCION — una linea por detector" | Write-Host
("=" * 100) | Write-Host

foreach ($g in ($fusionados | Group-Object tipo | Sort-Object Name)) {
    $m = $g.Group | Sort-Object puntaje -Descending | Select-Object -First 1
    $signo = if ([int]$m.signo -lt 0) { '-' } else { '+' }
    "`n[{0}] {1,-18} n={2,-4} pts={3}" -f $signo, $g.Name, $g.Count, $m.puntaje | Write-Host
    "    {0:yyyy-MM-dd}  {1}" -f [datetime]$m.fecha, $m.titular | Write-Host
    if ($m.situacion) { "    -> {0}" -f $m.situacion | Write-Host }
}

$vacios = $archivos | ForEach-Object { ($_.Name -replace '^\d+_', '') -replace '\.sql$', '' } |
          Where-Object { $_ -notin ($fusionados.tipo | Select-Object -Unique) }
if ($vacios) { "`n[ ] sin filas hoy: $($vacios -join ', ')" | Write-Host }

"`nLas 10 de mayor puntaje:" | Write-Host
$fusionados | Sort-Object puntaje -Descending | Select-Object -First 10 | ForEach-Object {
    "  {0,4}  {1:yyyy-MM-dd}  {2,-22} {3}" -f $_.puntaje, [datetime]$_.fecha, $_.nombre, $_.titular | Write-Host
}

# Un día sin efemérides es un día en blanco en la página. No es un error —hay días de enero sin nada—
# pero conviene verlo antes de subir, no después.
if ($dias -lt 200) {
    Write-Warning "Solo $dias dias del calendario tienen efemerides. Con los cumpleanos deberian ser >330."
}

# =====================================================================================
# 6. Las autocomprobaciones
# =====================================================================================
#
# POR QUÉ ESTÁN ACÁ Y NO EN UNA SUITE DE TESTS. El motor es PowerShell —por las razones de la 8.1 del
# diseño— y el gate del proyecto a un `.ps1` solo le mira la sintaxis: no hay `ruff`, ni `mypy`, ni
# `pytest`. Estas comprobaciones son lo que compensa eso, y no son teóricas: los dos primeros fallos
# reales de este motor —el juego perfecto rankeado por debajo de un no-hitter corriente, y «Cumple 46
# años. Es uno de los 923 dominicanos que lo ha logrado»— se cazaron MIRANDO LA SALIDA. Esto es
# mirarla sin depender de que alguien se acuerde.
#
# Avisan, no abortan: el CSV ya está escrito y es más útil poder revisarlo que no tenerlo.

$problemas = @()

# El puntaje vive en 0-1000 por construcción (600+200+150+50). Fuera de ahí, el motor se rompió.
$fuera = @($fusionados | Where-Object { [int]$_.puntaje -lt 0 -or [int]$_.puntaje -gt 1000 })
if ($fuera) { $problemas += "$($fuera.Count) fila(s) con puntaje fuera de 0-1000" }

# Una fila sin titular es una fila que la página no puede pintar.
$mudas = @($fusionados | Where-Object { [string]::IsNullOrWhiteSpace($_.titular) })
if ($mudas) { $problemas += "$($mudas.Count) fila(s) sin titular" }

# Una plantilla mal escrita deja el marcador crudo en el texto publicado.
$crudas = @($fusionados | Where-Object { $_.titular -match '\{[a-z_]+\}' })
if ($crudas) { $problemas += "$($crudas.Count) fila(s) con marcadores sin rellenar: $($crudas[0].titular)" }

# UNA DESHONRA NUNCA DEBE GANARLE A UNA HAZAÑA. Es la razón de ser de la escala partida (4.5): la
# rareza sola les daba lo mismo, porque ponchar 5 veces es tan raro como batear el ciclo.
$peorPositiva  = ($fusionados | Where-Object { [int]$_.signo -gt 0 } | Measure-Object puntaje -Minimum).Minimum
$mejorNegativa = ($fusionados | Where-Object { [int]$_.signo -lt 0 } | Measure-Object puntaje -Maximum).Maximum
if ($null -ne $mejorNegativa -and $mejorNegativa -gt 400) {
    $problemas += "una gesta negativa saca $mejorNegativa, por encima del techo de 400 de su escala"
}

# Con cobertura parcial NO se publica el total: el número que vemos es el de la ventana, no el de la
# historia. Ver 5.2.5.
$filtradas = @($fusionados | Where-Object { $_.cobertura -ne 'completa' -and $_.veces_total })
if ($filtradas) { $problemas += "$($filtradas.Count) fila(s) de cobertura parcial publican veces_total" }

# La fusión debe haber dejado una sola fila por jugador-juego-evento.
$repes = @($fusionados | Group-Object { "$($_.mlb_id)|$($_.game_id)|$($_.event_id)|$($_.fecha)" } | Where-Object { $_.Count -gt 1 })
if ($repes) { $problemas += "$($repes.Count) clave(s) repetida(s) tras la fusion" }

"" | Write-Host
if ($problemas) {
    foreach ($p in $problemas) { Write-Warning $p }
} else {
    Write-Host "Autocomprobaciones: todo en orden." -ForegroundColor Green
}
