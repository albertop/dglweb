-- =====================================================================================
-- EL WALK-OFF QUE ADEMÁS DIO VUELTA AL JUEGO: el equipo estaba PERDIENDO y ganó con ese batazo.
--
-- EL FILTRO DE «NO EMPATADO» LO PIDIÓ EL DUEÑO, y la medición explica por qué. De los 955 walk-off
-- dominicanos:
--
--     con el juego EMPATADO      847   <- el caso corriente: un sencillo y a casa
--     PERDIENDO                  108   <- este detector
--
-- Ocho de cada nueve walk-off son con el marcador igualado, y ahí el batazo rompe un empate: bonito,
-- pero es la forma normal en que se acaba un juego cerrado. Estar ABAJO y ganarlo en el mismo turno
-- es otra cosa — hay que empujar la carrera del empate y la de la ventaja de una sola vez, o sea un
-- extrabase con gente en base. Por eso los 108 se leen todos como noticia y los 847 no.
--
-- COMO EL EQUIPO DE CASA NO PUEDE ESTAR GANANDO cuando batea en el noveno o más allá —el juego ya
-- habría terminado—, «no empatado» y «perdiendo» son la misma condición. Se escribe `sc_bat <
-- sc_riv` porque dice lo que de verdad pasó.
--
-- LOS DETECTORES HERMANOS NO CAMBIAN. `61_walkoff_hr`, `62_walkoff_slam` y `64_walkoff_sin_batear`
-- siguen cubriendo los empatados dentro de su propia forma, que es lo que los hace específicos.
-- `63_walkoff_2outs` ya pedía «perdiendo» y ahora es un subconjunto estricto de este.
--
-- GRANO: turno al bate. Universo 822764. Sale de `#turnos` (preludio `_01_turnos.sql`).
--
-- Acá SÍ se nombra al lanzador: el turno se enfrentó a UN hombre, así que decirlo es verdad.
-- =====================================================================================
SELECT  'walkoff' AS tipo,
        'un walk-off estando abajo en el marcador' AS gesta,
        'bateador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        822764 AS universo,
        -- «WALK-OFF» Y NO «TERMINÓ EL JUEGO» (dueño, 2026-08-04). El término en inglés es el que la
        -- afición usa y entiende de una vez; la perífrasis en español es correcta y no dice nada.
        -- Vale para toda la familia: `61`, `62`, `63` y `64` llevan la misma cabeza.
        'Walk-off dándole la vuelta al juego contra {rival_nombre}, ante {oponente}: {detalle}.' AS plantilla,
        t.mlb_id, t.nombre, t.fecha, t.temporada, t.game_id, t.event_id, t.game_type,
        t.equipo, t.rival, t.en_casa,
        1 AS signo,
        t.wpa AS magnitud,
        t.wpa AS wpa_jugador,
        t.li AS li_max,
        'iban ' + CAST(t.sc_bat AS varchar(2)) + '-' + CAST(t.sc_riv AS varchar(2)) + ' abajo en el '
            + t.inning_txt
            + CASE WHEN t.outs = 0 THEN ', sin outs' WHEN t.outs = 1 THEN ', con 1 out' ELSE ', con ' + CAST(t.outs AS varchar(1)) + ' outs' END AS detalle,
        t.equipo_nombre, t.rival_nombre, t.oponente
FROM    #turnos t
WHERE   t.es_walkoff = 1
  -- PERDIENDO, NO EMPATADO. `sc_bat` y `sc_riv` son el marcador ANTES del turno, así que esto es
  -- «iba abajo cuando llegó al plato».
  AND   t.sc_bat < t.sc_riv;
