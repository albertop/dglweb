-- =====================================================================================
-- LA PALIZA, MEDIDA POR RITMO: valor de carreras por bateador enfrentado. Medido: 79 veces.
--
-- IDEA DEL DUEÑO (2026-08-04), y arregla un detector que estaba mal planteado.
--
-- QUÉ ESTABA MAL. La regla era «10 hits y 10 carreras» sobre el juego entero, y daba 19 casos en 116
-- temporadas. El problema no era el número, era el concepto: A UN LANZADOR NO LO DEJAN AHÍ PARA QUE
-- LE HAGAN DIEZ CARRERAS — LO SACAN. Aquella regla solo podía encontrar juegos en que al hombre lo
-- dejaron hasta el final, que es justo lo que NO pasa en una paliza. La paliza de verdad dura una
-- entrada. El dueño la descartó por eso: «no hace sentido».
--
-- LA MEDIDA BUENA ES UN RITMO, no un total, porque un total siempre premia al que estuvo más rato:
--
--     ritmo = suma del RUN_VALUE de sus bateadores / bateadores enfrentados
--
-- `RUN_VALUE` va desde la ofensiva, así que positivo es daño al lanzador. Dividir por bateadores
-- enfrentados quita el tiempo de la ecuación: mide CUÁNTO LE COSTÓ CADA HOMBRE, y con eso la
-- entrada catastrófica y el juego largo compiten en igualdad.
--
-- EL UMBRAL ES 1,0 Y SE EXPLICA SOLO: cada bateador que enfrentó le costó, en promedio, una carrera
-- entera. Medido sobre 64.540 juegos-lanzador dominicanos de al menos 3 bateadores:
--
--     ritmo >= 0,50    1.910 casos    16,47 por temporada
--     ritmo >= 0,70      630           5,43
--     ritmo >= 0,80      353           3,04
--     ritmo >= 1,00       79           0,68   <- el corte
--
-- 0,68 por temporada lo deja en la misma liga que `hr3` (0,55) y `triples2` (0,65). Y a diferencia
-- de 0,8 o 0,7, el 1,0 no hay que justificarlo: es la línea en que el lanzador regaló una carrera
-- por hombre.
--
-- EL MÍNIMO DE 3 BATEADORES no es un umbral más, es lo que impide que la métrica se rompa: con un
-- solo bateador enfrentado, un grand slam da un ritmo altísimo y eso no es una paliza, es un batazo.
--
-- `signo = -1`: corre a media escala en todo, con techo 400. Ver docs/EFEMERIDES.md 4.5.
--
-- GRANO: juego-jugador (292.948).
-- =====================================================================================
WITH ritmo AS (
    SELECT  e.GAME_ID AS game_id, e.PITCHER_ID AS retro_id,
            SUM(e.RUN_VALUE)                                  AS rv,
            COUNT(1)                                          AS bf,
            SUM(e.RUN_VALUE) / NULLIF(CAST(COUNT(1) AS float), 0) AS ritmo
    FROM    dbo.r24Events e
    INNER JOIN dbo.dglMaster m ON m.retroID = e.PITCHER_ID
    WHERE   e.BAT_EVENT_FL = 1
    GROUP BY e.GAME_ID, e.PITCHER_ID
    HAVING  COUNT(1) >= 3
        AND SUM(e.RUN_VALUE) / NULLIF(CAST(COUNT(1) AS float), 0) >= 1.0
)
SELECT  'paliza' AS tipo,
        'una salida de una carrera por bateador enfrentado' AS gesta,
        'lanzador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        292948 AS universo,
        -- El texto dice el ritmo con palabras, no con el número: «cada bateador… le costó una
        -- carrera» se entiende sin saber qué es el RUN_VALUE. Es la misma decisión que en
        -- `66_turno_clave.sql` con el leverage — el dato queda en la columna, no en la frase.
        'Le cayeron encima los {rival_nombre}: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0 AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        -1 AS signo,
        -- La MAGNITUD es el daño total, no el ritmo. El ritmo ya definió quién entra; entre los que
        -- entraron, la peor es la que más carreras costó de verdad.
        r.rv AS magnitud,
        NULL AS wpa_jugador,
        j.li_max,
        -- «EN 0 ENTRADAS» NO SE DICE. Un lanzador al que sacan sin retirar a nadie no lanzó cero
        -- entradas: no sacó un out, que es lo que hay que escribir. Y el número de bateadores va acá
        -- porque es la mitad de la medida — sin él, «le costó una carrera a cada uno» no se sostiene.
        CAST(j.P_R AS varchar(2)) + CASE WHEN j.P_R = 1 THEN ' carrera' ELSE ' carreras' END + ' y '
            + CAST(j.P_H AS varchar(2)) + CASE WHEN j.P_H = 1 THEN ' hit ' ELSE ' hits ' END
            + CASE WHEN j.P_OUT = 0
                   THEN 'sin sacar un solo out'
                   ELSE 'en ' + CAST(j.P_OUT / 3 AS varchar(3))
                        + CASE j.P_OUT % 3 WHEN 1 THEN '.1' WHEN 2 THEN '.2' ELSE '' END + ' entradas' END
            + ', una carrera por cada uno de los ' + CAST(r.bf AS varchar(3)) + ' bateadores que enfrentó' AS detalle,
        j.equipo_nombre, j.rival_nombre,
        '' AS oponente
FROM    ritmo r
INNER JOIN #juegos j ON j.game_id = r.game_id AND j.PLAYER_ID = r.retro_id;

-- =====================================================================================
-- LA LISTA — «¿cuáles son esas palizas?»
--
-- Se pega tal cual y corre sola: no depende de `#juegos`, que solo existe mientras el motor corre.
-- =====================================================================================
/*
WITH ritmo AS (
    SELECT  e.GAME_ID, e.PITCHER_ID,
            SUM(e.RUN_VALUE) AS rv, COUNT(1) AS bf,
            SUM(e.RUN_VALUE) / NULLIF(CAST(COUNT(1) AS float), 0) AS ritmo
    FROM    dbo.r24Events e
    INNER JOIN dbo.dglMaster m ON m.retroID = e.PITCHER_ID
    WHERE   e.BAT_EVENT_FL = 1
    GROUP BY e.GAME_ID, e.PITCHER_ID
    HAVING  COUNT(1) >= 3 AND SUM(e.RUN_VALUE) / NULLIF(CAST(COUNT(1) AS float), 0) >= 1.0
),
d AS (
    SELECT r.PLAYER_ID, r.GAME_ID, r.GAME_DT, r.P_OUT, r.P_H, r.P_R, r.P_ER, r.OPPONENT_ID
    FROM   dbo.retroDailyReg r
    UNION ALL
    SELECT p.PLAYER_ID, p.GAME_ID, p.GAME_DT, p.P_OUT, p.P_H, p.P_R, p.P_ER, p.OPPONENT_ID
    FROM   dbo.retroDailyPost p
)
SELECT  m.nameList AS lanzador, CAST(d.GAME_DT AS date) AS fecha, d.OPPONENT_ID AS rival,
        d.P_OUT / 3.0 AS entradas, d.P_H AS hits, d.P_R AS carreras,
        r.bf AS bateadores_enfrentados,
        CAST(r.ritmo AS decimal(5,2)) AS carreras_por_bateador
FROM    ritmo r
INNER JOIN d ON d.GAME_ID = r.GAME_ID AND d.PLAYER_ID = r.PITCHER_ID
INNER JOIN dbo.dglMaster m ON m.retroID = r.PITCHER_ID
ORDER BY r.ritmo DESC;
*/
