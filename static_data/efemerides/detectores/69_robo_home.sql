-- =====================================================================================
-- Robo de HOME.
--
-- GRANO PROPIO: veces en tercera base (92.821), no turnos al bate. Quien roba home no está bateando
-- — está en tercera. Medido: 85 robos de 53 corredores. Rareza 367.
--
-- ESTRENA EL `rol = corredor`, el quinto del contrato. El contrato asumía bateador, lanzador o
-- fildeador; esto no es ninguno de los tres. Ver docs/EFEMERIDES.md 3.1.
--
-- `RUN3_SB_FL = 'T'` es exactamente eso: el corredor de tercera se robó una base, y desde tercera
-- solo se puede robar home.
-- =====================================================================================
SELECT  'robo_home'                               AS tipo,
        'un robo de home' AS gesta,
        'corredor'                                AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        92821                                     AS universo,
        'Se robó el home contra {rival_nombre}: {detalle}.' AS plantilla,
        m.mlbID                                   AS mlb_id,
        m.nameList                                AS nombre,
        f.fecha,
        e.SEASON                                  AS temporada,
        e.GAME_ID                                 AS game_id,
        e.EVENT_ID                                AS event_id,
        'R'                                       AS game_type,
        CASE WHEN e.BAT_HOME_ID = 1 THEN g.HOME_TEAM_ID ELSE g.AWAY_TEAM_ID END AS equipo,
        CASE WHEN e.BAT_HOME_ID = 1 THEN g.AWAY_TEAM_ID ELSE g.HOME_TEAM_ID END AS rival,
        e.BAT_HOME_ID                             AS en_casa,
        1                                         AS signo,
        1                                         AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        'en el ' + CASE WHEN e.INN_CT >= 10 THEN 'inning ' + CAST(e.INN_CT AS varchar(2)) ELSE CASE e.INN_CT WHEN 1 THEN '1er' WHEN 2 THEN '2do' WHEN 3 THEN '3er' WHEN 4 THEN '4to' WHEN 5 THEN '5to' WHEN 6 THEN '6to' WHEN 7 THEN '7mo' WHEN 8 THEN '8vo' ELSE '9no' END END + CASE WHEN e.OUTS_CT = 0 THEN ', sin outs' WHEN e.OUTS_CT = 1 THEN ', con 1 out' ELSE ', con ' + CAST(e.OUTS_CT AS varchar(1)) + ' outs' END AS detalle,
        COALESCE(eq.nombre, '')                   AS equipo_nombre,
        COALESCE(ri.nombre, '')                   AS rival_nombre,
        COALESCE(lz.nombre, '')                   AS oponente
FROM    dbo.retroEventsReg e
INNER JOIN dbo.dglMaster m ON m.retroID = e.BASE3_RUN_ID
LEFT  JOIN #fechas  f  ON f.game_id = e.GAME_ID
LEFT  JOIN dbo.retroGamesReg g ON g.GAME_ID = e.GAME_ID
LEFT  JOIN #nombres lz ON lz.retro_id = e.PIT_ID
LEFT  JOIN #equipos eq ON eq.codigo = CASE WHEN e.BAT_HOME_ID = 1 THEN g.HOME_TEAM_ID ELSE g.AWAY_TEAM_ID END
                      AND f.fecha BETWEEN eq.desde AND eq.hasta
LEFT  JOIN #equipos ri ON ri.codigo = CASE WHEN e.BAT_HOME_ID = 1 THEN g.AWAY_TEAM_ID ELSE g.HOME_TEAM_ID END
                      AND f.fecha BETWEEN ri.desde AND ri.hasta
WHERE   e.RUN3_SB_FL = 'T';

-- =====================================================================================
-- LA LISTA — «¿quiénes se han robado el home?»
-- =====================================================================================
/*
SELECT  m.nameList AS corredor, CAST(g.GAME_DT AS date) AS fecha, e.SEASON AS temporada,
        e.INN_CT AS inning, e.OUTS_CT AS outs
FROM    dbo.retroEventsReg e
INNER JOIN dbo.dglMaster m ON m.retroID = e.BASE3_RUN_ID
LEFT  JOIN dbo.retroGamesReg g ON g.GAME_ID = e.GAME_ID
WHERE   e.RUN3_SB_FL = 'T'
ORDER BY g.GAME_DT;
*/
