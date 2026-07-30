"""El refresco diario como UNA unidad, en vez de diez horarios que se cruzan los dedos.

Antes cada job tenía su hora y apostaba a que el anterior había terminado: `build_leaders` corría a
las 7:30 pasara lo que pasara a las 6:30, y podía publicar liderazgos mezclando dato nuevo con viejo
sin que nada se enterara. `IngestRun` daba observabilidad por comando, pero no existía la entidad
«refresco del 26 de julio» que dijera si el día salió bien.

Acá los pasos corren en orden y **lo derivado depende de que las entradas hayan salido bien**. Esa es
toda la idea: los liderazgos son un RESULTADO, y publicar un resultado calculado sobre insumos rotos
es peor que no publicarlo — el sitio se ve sano y miente.

Tres decisiones que conviene entender antes de tocarlo:

**Las entradas se intentan todas, aunque una falle.** Abortar en el primer error dejaría sin saber si
el problema es uno o son tres, y mañana habría que descubrirlo de a uno. Se corren las tres y se
reporta el panorama completo.

**Publicar con insumos incompletos es una decisión explícita**, no el comportamiento por defecto:
`--publicar-parcial`. Sin esa bandera, un fallo en las entradas deja los derivados sin tocar y el
sitio sigue mostrando los de ayer — que están completos, aunque sean de ayer.

**La ventana de temporada se evalúa UNA vez, acá.** Los comandos hijos se llaman con `--force`
porque el pipeline ya decidió. Si cada uno volviera a mirar, en invierno se escribirían once filas
`skipped` por día en vez de una, y el log de ingesta pasaría de bitácora a ruido.
"""

from dataclasses import dataclass, field
from datetime import datetime

from django.core.management import call_command
from django.utils import timezone

from dglweb.core import notify
from dglweb.stats import locks, season_window
from dglweb.stats.models import IngestRun
from dglweb.stats.runlog import record_run, record_skip

# Los insumos del día: lo que el proxy trae y nosotros guardamos.
#
# `build_team_games` va PRIMERO y no con los derivados, aunque nada suyo dependa de las estadísticas:
# de él sale el umbral prorrateado que `build_leaders` aplica al final. Si corriera después, los
# tableros del día se construirían con los juegos de ayer — un día de menos, unas tres apariciones de
# umbral. Poco, pero gratis de evitar poniéndolo en el orden correcto.
ENTRADAS = ("build_team_games", "update_batting", "update_pitching", "update_fielding")
# Los de octubre, con su propia ventana: en junio no hay postemporada que buscar.
ENTRADAS_POST = ("update_batting_post", "update_pitching_post", "update_fielding_post")
# Lo que se CALCULA a partir de lo anterior. En orden: los líderes de por vida leen los totales.
DERIVADOS = ("build_career_totals", "build_leaders")
# Lo que alimenta los widgets de la portada. Lee del proxy, no de nuestras tablas, así que tampoco
# depende de que las entradas hayan salido bien: la jornada de ayer es la jornada de ayer.
PORTADA = ("build_daily_standouts", "build_game_videos")
# Lee la temporada desde la API, no nuestras tablas, así que no depende de las entradas.
AVISOS = ("detect_debuts",)
# Mantenimiento del propio log. Corre siempre, incluso fuera de temporada — ver el comando.
MANTENIMIENTO = ("prune_ingest_log",)

# Por qué se omitió un derivado. Va como prefijo para que el detalle diga QUIÉN lo dejó colgado:
# «build_leaders: skipped — omitido porque no terminó bien build_career_totals».
OMITIDO_POR = "omitido porque no terminó bien "

# Lo que se pone cuando el paso no dejó rastro. NO es una explicación del comando: es el marcador de
# que no sabemos nada de él. La diferencia importa en `_correr` — ver ahí.
SIN_FILA = "no dejó fila en el log"


@dataclass
class Paso:
    """Cómo salió un paso. `estado` es el de su propia fila en `IngestRun`, no el de la excepción."""

    comando: str
    estado: str
    filas: int = 0
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.estado == IngestRun.Status.SUCCESS

    @property
    def omitido(self) -> bool:
        """No se ejecutó a propósito, porque su dependencia no salió bien. NO es un fallo suyo.

        La distinción no es de vocabulario: si contara como fallo, el aviso diría que dos cosas se
        rompieron cuando se rompió una, y mandaría a revisar `build_leaders` en vez de a los totales de
        carrera, que es donde está el problema.
        """
        return self.estado == IngestRun.Status.SKIPPED

    def __str__(self) -> str:
        detalle = f" — {self.error}" if self.error else ""
        return f"{self.comando}: {self.estado} ({self.filas:,} filas){detalle}"


@dataclass
class Resultado:
    """El día entero. Lo que se guarda en la fila agregada de `IngestRun`."""

    pasos: list[Paso] = field(default_factory=list)
    derivados_publicados: bool = False
    motivo_salto: str = ""

    @property
    def fallidos(self) -> list[Paso]:
        """Los que se ejecutaron y salieron mal. Los OMITIDOS quedan fuera a propósito — ver `omitido`.

        Esta lista hace dos trabajos: decide si se publican los derivados, y es la que se marca en la
        fila agregada. En el primero no cambia nada al excluir los omitidos —los insumos nunca se
        omiten, solo fallan— y en el segundo evita acusar a un paso que ni corrió.
        """
        return [p for p in self.pasos if not p.ok and not p.omitido]

    @property
    def omitidos(self) -> list[Paso]:
        return [p for p in self.pasos if p.omitido]

    @property
    def filas(self) -> int:
        return sum(p.filas for p in self.pasos)


def _estado_de(comando: str, desde: datetime) -> Paso:
    """La fila que el comando acaba de escribir. Es la fuente de verdad, no si lanzó excepción.

    Un comando puede terminar sin excepción y aun así haber fallado a medias —`refresh_current`
    avisa por `stderr` y sigue—, y en ese caso su `IngestRun` queda en PARTIAL. Preguntarle al log es
    lo que hace que el orquestador vea lo mismo que ve el dueño en el Backoffice.
    """
    fila = IngestRun.objects.filter(command=comando, started_at__gte=desde).order_by("-started_at").first()
    if fila is None:
        # No dejó rastro: o reventó antes de registrarse, o no es un comando que registre. Se cuenta
        # como fallo — un paso del que no sabemos nada no puede tratarse como exitoso.
        return Paso(comando=comando, estado=IngestRun.Status.FAILED, error=SIN_FILA)
    return Paso(comando=comando, estado=fila.status, filas=fila.rows_affected, error=(fila.detail or "")[:200])


def _correr(comando: str, desde: datetime, note: object) -> Paso:
    """Corre un paso y devuelve cómo salió. Nunca propaga: el pipeline decide qué hacer con el fallo."""
    try:
        # `--force`: la ventana de temporada ya la evaluó el pipeline. Ver el docstring del módulo.
        call_command(comando, force=True)
    except Exception as error:  # cualquier fallo de un paso es dato del pipeline, no una interrupción
        paso = _estado_de(comando, desde)
        # El detalle que el propio comando dejó en su fila gana: sabe mejor que nosotros por qué
        # falló, y «el equipo BOS no existe en 1899» es más útil que el `RuntimeError` con el que
        # terminó reventando. Pero `SIN_FILA` NO es una explicación suya —es nuestro marcador de que
        # no sabemos nada— y acá sí sabemos: la excepción es justamente por qué no hay fila. Dejarlo
        # en «no dejó fila en el log» manda a buscar un problema de registro donde hubo un error, y
        # ese mensaje ya confundió una mañana entera.
        if paso.error in ("", SIN_FILA):
            paso.error = f"{type(error).__name__}: {error}"
        paso.estado = IngestRun.Status.FAILED
        if callable(note):
            note(f"  ✗ {paso}")
        return paso
    paso = _estado_de(comando, desde)
    if callable(note):
        note(f"  {'✓' if paso.ok else '✗'} {paso}")
    return paso


def _correr_cadena(comandos: tuple[str, ...], desde: datetime, note: object, resultado: Resultado) -> bool:
    """Corre una CADENA: si un paso no sale bien, los siguientes NO se ejecutan. Devuelve si publicó.

    ARCH-01 DEL REVIEW v13, Y ERA UN FALLO DE VERDAD
    ------------------------------------------------
    Antes esto era un `for` que llamaba a los dos derivados pasara lo que pasara, y
    `derivados_publicados` se ponía en `True` ANTES de empezar. Comprobado haciendo fallar
    `build_career_totals` a propósito: `build_leaders` se ejecutaba igual y el resultado decía que
    había publicado.

    Lo que eso produce no es una caída sino algo peor: **una foto mixta que se afirma completa.** Los
    liderazgos de por vida LEEN los totales de carrera, así que con los totales fallidos se
    reconstruían los rankings de temporada con datos de hoy y los de carrera con los de ayer. El aviso
    de Telegram decía que los derivados se publicaron, porque ese es el único sitio donde se mira el
    flag.

    Ahora la dependencia es real: `DERIVADOS` está en orden —los totales primero— y si uno no termina
    en `SUCCESS`, el siguiente se registra como OMITIDO y no se llama. El flag se pone al final y solo
    si la cadena entera salió bien.

    POR QUÉ SE REGISTRA EL OMITIDO en vez de callarlo: un paso que no aparece se lee como un paso que
    no existe. «build_leaders: omitido — build_career_totals no terminó bien» dice qué pasó y por qué,
    que es justo lo que el dueño necesita a las seis de la mañana.
    """
    for i, comando in enumerate(comandos):
        paso = _correr(comando, desde, note)
        resultado.pasos.append(paso)
        if not paso.ok:
            for pendiente in comandos[i + 1 :]:
                omitido = Paso(
                    comando=pendiente,
                    estado=IngestRun.Status.SKIPPED,
                    error=f"{OMITIDO_POR}{comando}",
                )
                resultado.pasos.append(omitido)
                if callable(note):
                    note(f"  - {omitido}")
            return False
    return True


def hay_trabajo(force: bool = False) -> tuple[bool, str]:
    """¿Hay algo que refrescar hoy? Devuelve también el motivo, para el log del salto.

    Vive aparte porque la decisión la necesitan dos: quien ejecuta y quien registra. Si cada uno la
    calculara por su cuenta podrían discrepar, y el caso feo sería abrir una fila de corrida para un
    día en el que no se hace nada.
    """
    regular = season_window.evaluate()
    octubre = season_window.evaluate(postseason=True)
    return (regular.corre or octubre.corre or force), regular.motivo


def run_daily(*, force: bool = False, publicar_parcial: bool = False, note: object = None) -> Resultado:
    """El refresco del día. Devuelve el panorama completo; el comando lo registra y lo imprime."""
    inicio = timezone.now()
    resultado = Resultado()

    regular = season_window.evaluate()
    octubre = season_window.evaluate(postseason=True)

    if not (regular.corre or octubre.corre or force):
        resultado.motivo_salto = regular.motivo
        return resultado

    if callable(note):
        note(f"Refresco diario — {regular.motivo}")

    if regular.corre or force:
        for comando in ENTRADAS:
            resultado.pasos.append(_correr(comando, inicio, note))
    if octubre.corre or force:
        for comando in ENTRADAS_POST:
            resultado.pasos.append(_correr(comando, inicio, note))

    # La decisión que da sentido a todo esto: no se publica lo derivado si los insumos no están.
    fallidos = resultado.fallidos
    if fallidos and not publicar_parcial:
        if callable(note):
            note(
                f"NO se reconstruyen los derivados: {len(fallidos)} paso(s) de entrada sin éxito. "
                "El sitio sigue mostrando los de ayer, que están completos. "
                "Para publicar igual: --publicar-parcial."
            )
    else:
        # Los dos derivados bajo el mismo candado, y no cada uno el suyo: son una cadena —los
        # liderazgos de por vida leen los totales de carrera— y protegerlos por separado deja que
        # otra cadena se cuele entre medio y publique líderes de una foto que ya no existe.
        with locks.cadena_derivada():
            resultado.derivados_publicados = _correr_cadena(DERIVADOS, inicio, note, resultado)

    for comando in (*PORTADA, *AVISOS):
        resultado.pasos.append(_correr(comando, inicio, note))
    return resultado


def run_and_record(*, force: bool = False, publicar_parcial: bool = False, note: object = None) -> Resultado:
    """`run_daily` con su fila agregada en el log — la entidad «refresco del día» que no existía.

    El mantenimiento del log va FUERA de la ventana de temporada y fuera del criterio de fallo: podar
    es higiene, no pelota, y tiene que correr los doce meses. Va al final para que pode incluyendo lo
    que este mismo refresco acaba de escribir.
    """
    hoy = timezone.localdate()
    corre, motivo = hay_trabajo(force)

    if not corre:
        record_skip("refresh_daily", str(hoy), motivo)
        resultado = Resultado(motivo_salto=motivo)
    else:
        # La fila se abre ANTES de trabajar, no después. Es lo que promete `record_run`: una corrida
        # en RUNNING hace visible un refresco colgado. Registrándola al final, la duración salía en
        # 0s para hora y media de trabajo y los pasos quedaban fuera de su ventana temporal.
        with record_run("refresh_daily", str(hoy)) as run:
            resultado = run_daily(force=force, publicar_parcial=publicar_parcial, note=note)
            run.add_rows(resultado.filas)
            for paso in resultado.pasos:
                run.note(str(paso))
            if not resultado.derivados_publicados:
                # LA CAUSA IMPORTA, y hasta el review v13 esta línea afirmaba una sola. Hay dos formas
                # de no publicar los derivados y mandan a mirar sitios distintos: que las ENTRADAS no
                # llegaran, o que un DERIVADO reventara. Decir siempre lo primero manda al dueño a
                # revisar el proxy cuando el problema está en nuestro propio cálculo.
                #
                # SE BUSCA EL DERIVADO ROTO, y no se deduce. La primera versión preguntaba si había
                # pasos OMITIDOS, y eso falla justo en un extremo: si el que revienta es `build_leaders`
                # —el último— no queda nada por omitir, así que la corrida decía «las entradas no
                # salieron completas» con todas las entradas en verde. El diagnóstico mandaba a mirar
                # el proxy con el fallo en nuestro propio cálculo.
                #
                # Y tampoco vale `fallidos[0]`: con `--publicar-parcial` la lista arranca con las
                # entradas que fallaron y se siguió igual, así que el primero puede ser un insumo que
                # no tuvo nada que ver con cortar la cadena.
                roto = next((p for p in resultado.fallidos if p.comando in DERIVADOS), None)
                if roto is not None:
                    run.note(f"Derivados NO reconstruidos: {roto.comando} no terminó bien y cortó la cadena.")
                else:
                    run.note("Derivados NO reconstruidos: las entradas no salieron completas.")
            for paso in resultado.fallidos:
                run.fail(paso.comando)  # deja la corrida en PARTIAL, visible en el Backoffice

    for comando in MANTENIMIENTO:
        call_command(comando)

    _avisar_si_falló(resultado, hoy)
    return resultado


def _avisar_si_falló(resultado: Resultado, hoy: object) -> None:
    """Telegram solo cuando hay algo roto. Un aviso diario de «todo bien» se vuelve ruido en una semana.

    El monitor externo que vigila `/health/pipeline` va a decir «503»; esto dice CUÁL paso, que es la
    diferencia entre enterarse y poder actuar sin abrir la computadora.
    """
    if not resultado.fallidos:
        return
    lineas = [f"⚠️ Refresco diario con fallos — {hoy}", ""]
    lineas += [f"• {paso}" for paso in resultado.fallidos]
    if not resultado.derivados_publicados:
        lineas += ["", "Los liderazgos NO se reconstruyeron: el sitio sigue mostrando los de ayer."]
    notify.enviar("\n".join(lineas))
