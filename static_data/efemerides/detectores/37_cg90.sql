-- =====================================================================================
-- Juego completo de menos de 90 lanzamientos. Medido: 8 veces, 7 lanzadores. Rareza 500.
--
-- DOS FILTROS QUE NO SON OPCIONALES, y sin ellos da 19 en vez de 8:
--
--   temporada >= 1989   el conteo de lanzamientos solo vale desde 1989 (regla del dueño): de los
--                       197 juegos completos dominicanos de los sesenta, solo 14 traen conteo.
--   P_OUT >= 27         P_CG incluye los acortados por lluvia. Sin esto entraba un juego de Ivan
--                       Nova de 57 lanzamientos que son 16 outs, o sea 5.1 entradas.
--
-- El universo tambien es propio: 251.106 juegos-jugador de 1989 en adelante. Es la regla del grano
-- aplicada al tiempo.
--
-- LA MAGNITUD VA AL REVES: menos lanzamientos es mas gesta, asi que se invierte.
--
-- Sale de `#juegos` (preludio `_00_comun.sql`). Sin abridor rival: gesta de juego completo.
-- =====================================================================================
SELECT  'cg90' AS tipo,
        'lanzador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        251106 AS universo,
        'Despachó a {rival_nombre} en juego completo con solo {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0 AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1 AS signo,
        (90 - j.P_PITCH) AS magnitud,
        j.wpa_pit AS wpa_jugador,
        j.li_max,
        CAST(j.P_PITCH AS varchar(3)) + ' lanzamientos' AS detalle,
        j.equipo_nombre, j.rival_nombre,
        '' AS oponente
FROM    #juegos j
WHERE   j.temporada >= 1989 AND j.P_PITCH > 0 AND j.P_PITCH < 90 AND j.P_OUT >= 27 AND j.P_CG >= 1;

-- =====================================================================================
-- LA LISTA — para cuando pregunten «¿quiénes son esos, y cuándo?»
--
-- Se pega tal cual en cualquier ventana de SQL Server y corre sola. NO usa `#juegos`: esa tabla la
-- crea el preludio y solo existe mientras el motor corre, así que una consulta que dependiera de
-- ella sería inútil justo cuando hace falta — con el dueño esperando la lista.
--
-- Por eso repite el UNION de `retroDailyReg` y `retroDailyPost`. Es duplicación deliberada: el
-- precio de que esto funcione sin preparar nada.
-- =====================================================================================
/*
WITH d AS (
    SELECT r.PLAYER_ID, r.GAME_ID, r.GAME_DT, r.SEASON, r.TEAM_ID, r.OPPONENT_ID, 'R' AS gt,
           r.B_AB, r.B_H, r.B_2B, r.B_3B, r.B_HR, r.B_RBI, r.B_R, r.B_BB, r.B_SO, r.B_SB, r.B_CS,
           r.B_TB, r.B_HP, r.B_GDP, r.P_CG, r.P_SHO, r.P_OUT, r.P_H, r.P_R, r.P_ER,
           r.P_BB, r.P_HP, r.P_SO, r.P_GDP, r.P_PITCH,
           (r.B_H - r.B_2B - r.B_3B - r.B_HR) AS B_1B
    FROM   dbo.retroDailyReg r INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
    UNION ALL
    SELECT p.PLAYER_ID, p.GAME_ID, p.GAME_DT, p.SEASON, p.TEAM_ID, p.OPPONENT_ID, 'P',
           p.B_AB, p.B_H, p.B_2B, p.B_3B, p.B_HR, p.B_RBI, p.B_R, p.B_BB, p.B_SO, p.B_SB, p.B_CS,
           p.B_TB, p.B_HP, p.B_GDP, p.P_CG, p.P_SHO, p.P_OUT, p.P_H, p.P_R, p.P_ER,
           p.P_BB, p.P_HP, p.P_SO, p.P_GDP, p.P_PITCH,
           (p.B_H - p.B_2B - p.B_3B - p.B_HR)
    FROM   dbo.retroDailyPost p INNER JOIN dbo.dglMaster m2 ON m2.retroID = p.PLAYER_ID
),
eq AS (
    SELECT t6.teamId AS codigo, t6.firstGame AS desde,
           CASE WHEN t6.lastGame < t6.firstGame THEN '9999-12-31' ELSE t6.lastGame END AS hasta,
           LTRIM(RTRIM(COALESCE(t6.location,'') + ' ' + COALESCE(t6.nickname,''))) AS nombre
    FROM   dbo.retroTeams_6d t6
    UNION ALL
    SELECT t.team, DATEFROMPARTS(t.firstSeason,1,1), DATEFROMPARTS(t.lastSeason,12,31),
           LTRIM(RTRIM(COALESCE(t.city,'') + ' ' + COALESCE(t.nickname,'')))
    FROM   dbo.retroTeams t
    WHERE  NOT EXISTS (SELECT 1 FROM dbo.retroTeams_6d x WHERE x.teamId = t.team)
)
SELECT  m.nameList                AS jugador,
        CAST(d.GAME_DT AS date)   AS fecha,
        d.SEASON                  AS temporada,
        CASE d.gt WHEN 'P' THEN 'postemporada' ELSE 'regular' END AS tipo_juego,
        COALESCE(pr.nombre, d.TEAM_ID)     AS equipo,
        COALESCE(ri.nombre, d.OPPONENT_ID) AS rival,
        d.P_OUT / 3.0 AS entradas, d.P_H AS hits_permitidos, d.P_R AS carreras, d.P_ER AS limpias,
        d.P_SO AS ponches, d.P_BB AS boletos, d.P_HP AS pelotazos,
        d.P_PITCH AS lanzamientos
FROM    d
INNER JOIN dbo.dglMaster m ON m.retroID = d.PLAYER_ID
LEFT  JOIN eq pr ON pr.codigo = d.TEAM_ID     AND d.GAME_DT BETWEEN pr.desde AND pr.hasta
LEFT  JOIN eq ri ON ri.codigo = d.OPPONENT_ID AND d.GAME_DT BETWEEN ri.desde AND ri.hasta
WHERE   d.SEASON >= 1989 AND d.P_PITCH > 0 AND d.P_PITCH < 90 AND d.P_OUT >= 27 AND d.P_CG >= 1
ORDER BY d.GAME_DT;
*/
