-- =====================================================================================
-- El ciclo inverso: jonrón, triple, doble y sencillo EN ESE ORDEN.
--
-- GRANO: juego-jugador. Universo 292.948.
-- Medido: 1 vez. Carlos Gómez, 2008-05-07. Rareza 600 — es único.
--
-- POR QUÉ NO SALE DE `retroDaily`: esa tabla dice CUÁNTOS batazos de cada tipo hubo, no en qué
-- orden. El orden solo está en `r24Events`, comparando el `EVENT_ID` del PRIMER batazo de cada tipo.
--
-- El hermano de este detector —`11_ciclo_natural.sql`, el orden ascendente— hoy devuelve CERO: en
-- 116 años ningún dominicano ha bateado un ciclo natural. Se escribe igual; cuesta nada y empieza a
-- producir el día que pase. Ver docs/EFEMERIDES.md 5.2.10.
-- =====================================================================================
WITH e AS (
    SELECT v.GAME_ID, v.BATTER_ID, v.SEASON, v.GAME_TYPE, v.EVENT_ID, v.BAT_HOME_ID,
           v.AWAY_TEAM_ID, v.HOME_TEAM_ID, v.[1B] AS s1, v.[2B] AS s2, v.[3B] AS s3, v.HR, v.WPA, v.LI
    FROM   dbo.r24Events v
    INNER JOIN dbo.dglMaster m ON m.retroID = v.BATTER_ID
    WHERE  v.BAT_EVENT_FL = 1
),
orden AS (
    SELECT GAME_ID, BATTER_ID,
           MIN(SEASON)                                  AS temporada,
           MIN(GAME_TYPE)                               AS gt,
           MIN(BAT_HOME_ID)                             AS en_casa,
           MIN(AWAY_TEAM_ID)                            AS visita,
           MIN(HOME_TEAM_ID)                            AS casa,
           SUM(WPA)                                     AS wpa,
           MAX(LI)                                      AS li,
           MIN(CASE WHEN s1 = 1 THEN EVENT_ID END)      AS e1,
           MIN(CASE WHEN s2 = 1 THEN EVENT_ID END)      AS e2,
           MIN(CASE WHEN s3 = 1 THEN EVENT_ID END)      AS e3,
           MIN(CASE WHEN HR = 1 THEN EVENT_ID END)      AS e4
    FROM   e
    GROUP BY GAME_ID, BATTER_ID
)
SELECT  'ciclo_inverso'                           AS tipo,
        'bateador'                                AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        292948                                    AS universo,
        'Bateó para el ciclo AL REVÉS: jonrón, triple, doble y sencillo, en ese orden.' AS plantilla,
        m.mlbID                                   AS mlb_id,
        m.nameList                                AS nombre,
        CAST(COALESCE(g.GAME_DT, gp.GAME_DT) AS date) AS fecha,
        o.temporada                               AS temporada,
        o.GAME_ID                                 AS game_id,
        0                                         AS event_id,
        o.gt                                      AS game_type,
        CASE WHEN o.en_casa = 1 THEN o.casa   ELSE o.visita END AS equipo,
        CASE WHEN o.en_casa = 1 THEN o.visita ELSE o.casa   END AS rival,
        o.en_casa                                 AS en_casa,
        1                                         AS signo,
        -- Único en la historia, así que la magnitud no separa nada. Se deja en 1 para no inventar
        -- una escala que no existe: el puntaje lo decide la rareza, que ya está en el tope.
        1                                         AS magnitud,
        o.wpa                                     AS wpa_jugador,
        o.li                                      AS li_max,
        'el único ciclo inverso de un dominicano'  AS detalle
FROM    orden o
INNER JOIN dbo.dglMaster m ON m.retroID = o.BATTER_ID
LEFT  JOIN dbo.retroGamesReg  g  ON g.GAME_ID  = o.GAME_ID
LEFT  JOIN dbo.retroGamesPost gp ON gp.GAME_ID = o.GAME_ID
WHERE   o.e4 < o.e3 AND o.e3 < o.e2 AND o.e2 < o.e1;
