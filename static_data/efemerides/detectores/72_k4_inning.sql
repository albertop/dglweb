-- =====================================================================================
-- CUATRO ponches en la misma entrada.
--
-- Solo se puede si un strike tres se le escapa al receptor y el bateador llega a primera: el
-- lanzador poncha a cuatro y solo saca tres outs.
--
-- Medido: CINCO dominicanos, de solo 100 en toda la liga en 116 años. Nadie ha ponchado 5 jamás.
-- Rareza 520 — entre el no-hitter (490) y el juego perfecto (600).
--
--     1984-05-17  Mario Soto, 3er inning        2018-07-08  Miguel Díaz, inning 11
--     2003-06-11  Octavio Dotel, 8vo            2021-07-25  Domingo Germán, 7mo
--     2012-06-05  Francisco Liriano, 4to
--
-- GRANO PROPIO: MEDIAS ENTRADAS LANZADAS por dominicanos (162.797). No son turnos ni juegos, y no
-- comparte universo ni con `nobletiger` —que también es de lanzador— porque uno se pregunta «de cada
-- bateador que enfrentó» y este «de cada entrada que lanzó». Es la regla del GRANO, no la del rol:
-- ver docs/EFEMERIDES.md 5.2.11.
-- =====================================================================================
WITH porInning AS (
    SELECT  v.GAME_ID, v.INN_CT, v.BAT_HOME_ID, v.PITCHER_ID,
            MIN(v.SEASON)          AS temporada,
            MIN(v.GAME_TYPE)       AS game_type,
            MIN(v.EVENT_ID)        AS primer_evento,
            SUM(CAST(v.SO AS int)) AS k
    FROM    dbo.r24Events v
    INNER JOIN dbo.dglMaster m ON m.retroID = v.PITCHER_ID
    WHERE   v.BAT_EVENT_FL = 1 AND v.GAME_TYPE = 'R'
    GROUP BY v.GAME_ID, v.INN_CT, v.BAT_HOME_ID, v.PITCHER_ID
    HAVING  SUM(CAST(v.SO AS int)) >= 4
)
SELECT  'k4_inning'                               AS tipo,
        '4 ponches en una sola entrada' AS gesta,
        'lanzador'                                AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        159014                                    AS universo,
        'Ponchó a {magnitud} en una sola entrada contra {rival_nombre}: {detalle}.' AS plantilla,
        m.mlbID                                   AS mlb_id,
        m.nameList                                AS nombre,
        f.fecha,
        p.temporada,
        p.GAME_ID                                 AS game_id,
        p.primer_evento                           AS event_id,
        p.game_type,
        -- El lanzador está en el equipo que NO batea.
        CASE WHEN p.BAT_HOME_ID = 1 THEN g.AWAY_TEAM_ID ELSE g.HOME_TEAM_ID END AS equipo,
        CASE WHEN p.BAT_HOME_ID = 1 THEN g.HOME_TEAM_ID ELSE g.AWAY_TEAM_ID END AS rival,
        CASE WHEN p.BAT_HOME_ID = 1 THEN 0 ELSE 1 END AS en_casa,
        1                                         AS signo,
        p.k                                       AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        'tres outs en el ' + CASE WHEN p.INN_CT >= 10 THEN 'inning ' + CAST(p.INN_CT AS varchar(2)) ELSE CASE p.INN_CT WHEN 1 THEN '1er' WHEN 2 THEN '2do' WHEN 3 THEN '3er' WHEN 4 THEN '4to' WHEN 5 THEN '5to' WHEN 6 THEN '6to' WHEN 7 THEN '7mo' WHEN 8 THEN '8vo' ELSE '9no' END END + ', porque un strike tres se le escapó al receptor' AS detalle,
        COALESCE(eq.nombre, '')                   AS equipo_nombre,
        COALESCE(ri.nombre, '')                   AS rival_nombre,
        ''                                        AS oponente
FROM    porInning p
INNER JOIN dbo.dglMaster m ON m.retroID = p.PITCHER_ID
LEFT  JOIN #fechas f ON f.game_id = p.GAME_ID
LEFT  JOIN dbo.retroGamesReg g ON g.GAME_ID = p.GAME_ID
LEFT  JOIN #equipos eq ON eq.codigo = CASE WHEN p.BAT_HOME_ID = 1 THEN g.AWAY_TEAM_ID ELSE g.HOME_TEAM_ID END
                      AND f.fecha BETWEEN eq.desde AND eq.hasta
LEFT  JOIN #equipos ri ON ri.codigo = CASE WHEN p.BAT_HOME_ID = 1 THEN g.HOME_TEAM_ID ELSE g.AWAY_TEAM_ID END
                      AND f.fecha BETWEEN ri.desde AND ri.hasta;

-- =====================================================================================
-- LA LISTA — «¿quiénes ponchan a cuatro en una entrada?»
--
-- Trae toda la liga marcando a los dominicanos: son 5 de 100 en 116 años, y ese contraste es la
-- noticia.
-- =====================================================================================
/*
WITH porInning AS (
    SELECT v.GAME_ID, v.INN_CT, v.PITCHER_ID, SUM(CAST(v.SO AS int)) AS k
    FROM   dbo.r24Events v WHERE v.BAT_EVENT_FL = 1
    GROUP BY v.GAME_ID, v.INN_CT, v.BAT_HOME_ID, v.PITCHER_ID
    HAVING SUM(CAST(v.SO AS int)) >= 4
)
SELECT  COALESCE(dm.nameList,
                 LTRIM(RTRIM(COALESCE(NULLIF(rm.nickname,''), rm.first, '') + ' ' + COALESCE(rm.last,'')))) AS lanzador,
        CASE WHEN dm.mlbID IS NOT NULL THEN 'dominicano' ELSE '' END AS dom,
        CAST(g.GAME_DT AS date) AS fecha, p.INN_CT AS inning, p.k AS ponches
FROM    porInning p
LEFT  JOIN dbo.retroMaster rm ON rm.playerID = p.PITCHER_ID
LEFT  JOIN dbo.dglMaster  dm ON dm.retroID  = p.PITCHER_ID
LEFT  JOIN dbo.retroGamesReg g ON g.GAME_ID = p.GAME_ID
ORDER BY g.GAME_DT;
*/
