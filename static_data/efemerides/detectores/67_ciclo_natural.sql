-- =====================================================================================
-- El ciclo NATURAL: sencillo, doble, triple y jonrón EN ESE ORDEN.
--
-- HOY DEVUELVE CERO. Ningún dominicano ha bateado un ciclo natural en 116 años — de los 20 ciclos,
-- ninguno salió en orden ascendente. Se escribe igual, por lo mismo que `sombrero_titanio`: cuesta
-- nada y empieza a producir el día que pase. Un detector vacío es una apuesta gratis.
--
-- GRANO: turno al bate (822.764), porque el orden solo existe a nivel de evento. `retroDaily` dice
-- CUÁNTOS batazos de cada tipo hubo, nunca en qué orden — por eso este detector no puede salir de
-- `#juegos` como el `ciclo` normal.
--
-- El hermano `12_ciclo_inverso.sql` sí tiene uno: Carlos Gómez, 2008-05-07.
-- =====================================================================================
WITH prim AS (
    SELECT  t.game_id, t.mlb_id, t.retro_id,
            MIN(CASE WHEN t.s1 = 1 THEN t.event_id END) AS e1,
            MIN(CASE WHEN t.s2 = 1 THEN t.event_id END) AS e2,
            MIN(CASE WHEN t.s3 = 1 THEN t.event_id END) AS e3,
            MIN(CASE WHEN t.hr = 1 THEN t.event_id END) AS e4
    FROM    #turnos t
    GROUP BY t.game_id, t.mlb_id, t.retro_id
),
-- El turno del jonrón, que es el que cierra el ciclo: de ahí salen la fecha, el rival y el lanzador.
cierre AS (
    SELECT  p.game_id, p.mlb_id, p.e4,
            p.e1, p.e2, p.e3
    FROM    prim p
    WHERE   p.e1 < p.e2 AND p.e2 < p.e3 AND p.e3 < p.e4
)
SELECT  'ciclo_natural'                           AS tipo,
        'un ciclo natural' AS gesta,
        'bateador'                                AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        811955                                    AS universo,
        'Bateó para el ciclo natural contra {rival_nombre}: sencillo, doble, triple y jonrón, en ese orden.' AS plantilla,
        t.mlb_id, t.nombre, t.fecha, t.temporada, t.game_id, t.event_id, t.game_type,
        t.equipo, t.rival, t.en_casa,
        1                                         AS signo,
        1                                         AS magnitud,
        t.wpa                                     AS wpa_jugador,
        t.li                                      AS li_max,
        'el único ciclo natural de un dominicano' AS detalle,
        t.equipo_nombre, t.rival_nombre, t.oponente
FROM    cierre c
INNER JOIN #turnos t ON t.game_id = c.game_id AND t.event_id = c.e4 AND t.mlb_id = c.mlb_id;

-- =====================================================================================
-- LA LISTA — para cuando pregunten «¿quiénes son esos, y cuándo?»
--
-- Se pega tal cual y corre sola. Devuelve LOS DOS ÓRDENES —natural e inverso— porque la pregunta
-- viene junta. Hoy el natural sale vacío.
-- =====================================================================================
/*
WITH e AS (
    SELECT v.GAME_ID, v.BATTER_ID, v.EVENT_ID, v.[1B] AS s1, v.[2B] AS s2, v.[3B] AS s3, v.HR
    FROM   dbo.r24Events v INNER JOIN dbo.dglMaster m ON m.retroID = v.BATTER_ID
    WHERE  v.BAT_EVENT_FL = 1
),
prim AS (
    SELECT GAME_ID, BATTER_ID,
           MIN(CASE WHEN s1 = 1 THEN EVENT_ID END) AS e1,
           MIN(CASE WHEN s2 = 1 THEN EVENT_ID END) AS e2,
           MIN(CASE WHEN s3 = 1 THEN EVENT_ID END) AS e3,
           MIN(CASE WHEN HR = 1 THEN EVENT_ID END) AS e4
    FROM   e GROUP BY GAME_ID, BATTER_ID
)
SELECT  m.nameList              AS jugador,
        CAST(g.GAME_DT AS date) AS fecha,
        CASE WHEN p.e1 < p.e2 AND p.e2 < p.e3 AND p.e3 < p.e4 THEN 'natural' ELSE 'inverso' END AS orden
FROM    prim p
INNER JOIN dbo.dglMaster m ON m.retroID = p.BATTER_ID
LEFT  JOIN dbo.retroGamesReg g ON g.GAME_ID = p.GAME_ID
WHERE   p.e1 IS NOT NULL AND p.e2 IS NOT NULL AND p.e3 IS NOT NULL AND p.e4 IS NOT NULL
  AND   ((p.e1 < p.e2 AND p.e2 < p.e3 AND p.e3 < p.e4) OR (p.e4 < p.e3 AND p.e3 < p.e2 AND p.e2 < p.e1))
ORDER BY g.GAME_DT;
*/
