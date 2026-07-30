# Genera el PDF de especificaciones que se le entrega a los anunciantes.
#
#   .\docs\generar_pdf_banners.ps1
#
# La FUENTE es `docs/ESPECIFICACIONES_BANNERS.md`. El PDF se regenera desde ahí, así que las
# correcciones se hacen en el Markdown y nunca sobre el PDF — si no, la próxima vez que alguien lo
# regenere se pierden.
#
# Se hace en dos pasos y con dos contenedores porque ninguna herramienta hace bien las dos cosas:
#
#   pandoc      Markdown → HTML5
#   WeasyPrint  HTML + CSS → PDF
#
# WeasyPrint y no LaTeX: acá el documento es tipografía y tablas, no fórmulas, y con CSS se controla
# el diseño con lo que ya sabemos usar. LaTeX daría un resultado correcto tras pelear con paquetes de
# acentuación y márgenes.
#
# El diseño vive en `docs/_banners.css`. Los colores son los de la marca, para que el documento se
# reconozca como nuestro sin llevar el logotipo repetido.
$ErrorActionPreference = 'Stop'

$fuente = 'ESPECIFICACIONES_BANNERS.md'
$salida = 'Especificaciones-banners-DGL.pdf'

# BARRAS NORMALES EN LA RUTA DEL MONTAJE. Docker Desktop admite las dos, pero una ruta de Windows con
# contrabarras dentro de un argumento `-v` se interpreta mal en cuanto aparece un espacio en el
# nombre de una carpeta — y este proyecto vive bajo `C:\Users\…\Documents`.
$dir = $PSScriptRoot -replace '\\', '/'

function Invocar-Docker {
    param([string[]]$Argumentos, [string]$Paso)

    & docker @Argumentos
    # `$ErrorActionPreference = 'Stop'` NO detiene un ejecutable externo que devuelve error: solo
    # actúa sobre los cmdlets de PowerShell. Sin esta comprobación, un fallo de pandoc seguiría
    # adelante y WeasyPrint intentaría convertir un HTML viejo o inexistente — dando un PDF
    # desactualizado sin que nada lo dijera.
    if ($LASTEXITCODE -ne 0) {
        throw "$Paso falló (código $LASTEXITCODE). El PDF NO se regeneró."
    }
}

Write-Host '1/2  Markdown -> HTML...'
Invocar-Docker -Paso 'pandoc' -Argumentos @(
    'run', '--rm', '-v', "${dir}:/data", 'pandoc/core:latest',
    '-f', 'markdown', '-t', 'html5', '--standalone',
    '--metadata', 'title=Especificaciones para banners',
    '-c', '_banners.css', '-o', '_banners.html', $fuente
)

Write-Host '2/2  HTML -> PDF...'
# El entrypoint de la imagen YA es `weasyprint`: pasar el nombre otra vez da «unrecognized arguments»
# y manda a buscar el problema en el archivo, que es donde no está.
Invocar-Docker -Paso 'WeasyPrint' -Argumentos @(
    'run', '--rm', '-v', "${dir}:/data", '-w', '/data',
    'ghcr.io/weasyprint/weasyprint:latest', '_banners.html', $salida
)

Remove-Item (Join-Path $PSScriptRoot '_banners.html') -ErrorAction SilentlyContinue

$pdf = Join-Path $PSScriptRoot $salida
$kb = [math]::Round((Get-Item $pdf).Length / 1KB)
Write-Host ''
Write-Host "Listo: docs/$salida  ($kb KB)"
