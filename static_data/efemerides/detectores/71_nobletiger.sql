-- =====================================================================================
-- NOBLETIGER — No-Outs Bases-Loaded Ending with Team Incapable of Getting Easy Run.
--
-- El lanzador se encuentra BASES LLENAS Y NINGÚN OUT, y sale del inning sin permitir carrera.
--
-- Medido: los dominicanos enfrentaron esa situación 2.522 veces y escaparon 324 — el 12,9 %.
-- Cuarenta y cuatro escapes fueron en el noveno o más, seis en postemporada. Rareza 340.
--
-- GRANO: bateadores enfrentados por dominicanos (622.652), NO turnos al bate. Es un detector de
-- lanzador y su universo es el suyo — ver docs/EFEMERIDES.md 5.2.11.
--
-- LA MAGNITUD ES EL WPA DEL ESCAPE, NO EL LI DEL MOMENTO, y se probaron las dos. Con LI el máximo
-- entre los 324 escapes es 1,44 y no separa nada. Sumando el WPA del lanzador desde el aprieto hasta
-- el final de la media entrada, la escala se abre de golpe:
--
--     2016-07-19  Jeurys Familia, 9no        +0,890
--     2012-09-29  Kelvin Herrera, inning 14  +0,878
--     2004-04-27  Francisco Cordero, 9no     +0,877
--
-- Un escape de +0,890 es ganar el juego prácticamente solo.
-- =====================================================================================
WITH jam AS (
    SELECT  v.GAME_ID, v.EVENT_ID, v.SEASON, v.GAME_TYPE, v.INN_CT, v.BAT_HOME_ID, v.PITCHER_ID,
            CASE WHEN v.BAT_HOME_ID = 1 THEN v.HOME_SCORE_CT ELSE v.AWAY_SCORE_CT END AS sc0
    FROM    dbo.r24Events v
    INNER JOIN dbo.dglMaster m ON m.retroID = v.PITCHER_ID
    WHERE   v.RUNNERS = '111' AND v.OUTS_CT = 0
),
-- ¿Entró carrera? Se compara el marcador del equipo al bate EN EL APRIETO contra el que tiene cuando
-- le toca batear otra vez.
--
-- EL COALESCE NO ES DEFENSIVO, ES NECESARIO: en 182 de los 2.522 casos el juego TERMINÓ en esa misma
-- media entrada, así que no hay «próxima vez al bate». Hay que caer al marcador final, y buscarlo en
-- las DOS tablas de juegos — con solo retroGamesReg quedaban 2 casos de postemporada sin resolver.
res AS (
    SELECT  j.GAME_ID, j.EVENT_ID, j.SEASON, j.GAME_TYPE, j.INN_CT, j.BAT_HOME_ID, j.PITCHER_ID, j.sc0,
            COALESCE(
                (SELECT TOP 1 CASE WHEN j.BAT_HOME_ID = 1 THEN e2.HOME_SCORE_CT ELSE e2.AWAY_SCORE_CT END
                 FROM   dbo.r24Events e2
                 WHERE  e2.GAME_ID = j.GAME_ID AND e2.EVENT_ID > j.EVENT_ID
                   AND  NOT (e2.INN_CT = j.INN_CT AND e2.BAT_HOME_ID = j.BAT_HOME_ID)
                 ORDER BY e2.EVENT_ID),
                (SELECT CASE WHEN j.BAT_HOME_ID = 1 THEN g.HOME_SCORE_CT ELSE g.AWAY_SCORE_CT END
                 FROM   dbo.retroGamesReg g WHERE g.GAME_ID = j.GAME_ID),
                (SELECT CASE WHEN j.BAT_HOME_ID = 1 THEN gp.HOME_SCORE_CT ELSE gp.AWAY_SCORE_CT END
                 FROM   dbo.retroGamesPost gp WHERE gp.GAME_ID = j.GAME_ID)
            ) AS sc_fin
    FROM    jam j
),
escapes AS (
    SELECT  r.GAME_ID, r.EVENT_ID, r.SEASON, r.GAME_TYPE, r.INN_CT, r.BAT_HOME_ID, r.PITCHER_ID,
            -SUM(v.WPA) AS wpa_escape
    FROM    res r
    INNER JOIN dbo.r24Events v
            ON v.GAME_ID = r.GAME_ID AND v.INN_CT = r.INN_CT
           AND v.BAT_HOME_ID = r.BAT_HOME_ID AND v.EVENT_ID >= r.EVENT_ID
    WHERE   r.sc_fin = r.sc0
    GROUP BY r.GAME_ID, r.EVENT_ID, r.SEASON, r.GAME_TYPE, r.INN_CT, r.BAT_HOME_ID, r.PITCHER_ID
)
SELECT  'nobletiger'                              AS tipo,
        'lanzador'                                AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        622652                                    AS universo,
        'Salió vivo de bases llenas sin outs contra {rival_nombre}: {detalle}.' AS plantilla,
        m.mlbID                                   AS mlb_id,
        m.nameList                                AS nombre,
        f.fecha,
        e.SEASON                                  AS temporada,
        e.GAME_ID                                 AS game_id,
        e.EVENT_ID                                AS event_id,
        e.GAME_TYPE                               AS game_type,
        -- El lanzador está en el equipo que NO batea, así que los lados van al revés que en los
        -- detectores de bateo. Es la vuelta que se olvida.
        CASE WHEN e.BAT_HOME_ID = 1 THEN g.AWAY_TEAM_ID ELSE g.HOME_TEAM_ID END AS equipo,
        CASE WHEN e.BAT_HOME_ID = 1 THEN g.HOME_TEAM_ID ELSE g.AWAY_TEAM_ID END AS rival,
        CASE WHEN e.BAT_HOME_ID = 1 THEN 0 ELSE 1 END AS en_casa,
        1                                         AS signo,
        e.wpa_escape                              AS magnitud,
        e.wpa_escape                              AS wpa_jugador,
        NULL                                      AS li_max,
        'en el ' + CASE WHEN e.INN_CT >= 10 THEN 'inning ' + CAST(e.INN_CT AS varchar(2)) ELSE CASE e.INN_CT WHEN 1 THEN '1er' WHEN 2 THEN '2do' WHEN 3 THEN '3er' WHEN 4 THEN '4to' WHEN 5 THEN '5to' WHEN 6 THEN '6to' WHEN 7 THEN '7mo' WHEN 8 THEN '8vo' ELSE '9no' END END + ', y no le anotaron' AS detalle,
        COALESCE(eq.nombre, '')                   AS equipo_nombre,
        COALESCE(ri.nombre, '')                   AS rival_nombre,
        ''                                        AS oponente
FROM    escapes e
INNER JOIN dbo.dglMaster m ON m.retroID = e.PITCHER_ID
LEFT  JOIN #fechas f ON f.game_id = e.GAME_ID
LEFT  JOIN dbo.retroGamesReg g ON g.GAME_ID = e.GAME_ID
LEFT  JOIN #equipos eq ON eq.codigo = CASE WHEN e.BAT_HOME_ID = 1 THEN g.AWAY_TEAM_ID ELSE g.HOME_TEAM_ID END
                      AND f.fecha BETWEEN eq.desde AND eq.hasta
LEFT  JOIN #equipos ri ON ri.codigo = CASE WHEN e.BAT_HOME_ID = 1 THEN g.HOME_TEAM_ID ELSE g.AWAY_TEAM_ID END
                      AND f.fecha BETWEEN ri.desde AND ri.hasta;

-- =====================================================================================
-- LA LISTA — «¿quiénes han salido vivos de bases llenas sin outs?»
--
-- Trae también los que NO escaparon, porque la proporción es la mitad de la noticia: 324 de 2.522,
-- el 12,9 %.
-- =====================================================================================
/*
WITH jam AS (
    SELECT v.GAME_ID, v.EVENT_ID, v.SEASON, v.INN_CT, v.BAT_HOME_ID, v.PITCHER_ID,
           CASE WHEN v.BAT_HOME_ID = 1 THEN v.HOME_SCORE_CT ELSE v.AWAY_SCORE_CT END AS sc0
    FROM   dbo.r24Events v INNER JOIN dbo.dglMaster m ON m.retroID = v.PITCHER_ID
    WHERE  v.RUNNERS = '111' AND v.OUTS_CT = 0
)
SELECT  m.nameList AS lanzador, CAST(g.GAME_DT AS date) AS fecha, j.SEASON AS temporada,
        j.INN_CT AS inning,
        CASE WHEN j.sc0 = COALESCE(
                (SELECT TOP 1 CASE WHEN j.BAT_HOME_ID = 1 THEN e2.HOME_SCORE_CT ELSE e2.AWAY_SCORE_CT END
                 FROM dbo.r24Events e2 WHERE e2.GAME_ID = j.GAME_ID AND e2.EVENT_ID > j.EVENT_ID
                   AND NOT (e2.INN_CT = j.INN_CT AND e2.BAT_HOME_ID = j.BAT_HOME_ID) ORDER BY e2.EVENT_ID),
                (SELECT CASE WHEN j.BAT_HOME_ID = 1 THEN g2.HOME_SCORE_CT ELSE g2.AWAY_SCORE_CT END
                 FROM dbo.retroGamesReg g2 WHERE g2.GAME_ID = j.GAME_ID),
                (SELECT CASE WHEN j.BAT_HOME_ID = 1 THEN gp.HOME_SCORE_CT ELSE gp.AWAY_SCORE_CT END
                 FROM dbo.retroGamesPost gp WHERE gp.GAME_ID = j.GAME_ID))
             THEN 'ESCAPO' ELSE 'le anotaron' END AS resultado
FROM    jam j
INNER JOIN dbo.dglMaster m ON m.retroID = j.PITCHER_ID
LEFT  JOIN dbo.retroGamesReg g ON g.GAME_ID = j.GAME_ID
ORDER BY g.GAME_DT;
*/
