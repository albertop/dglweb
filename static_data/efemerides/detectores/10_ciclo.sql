-- =====================================================================================
-- El ciclo: sencillo, doble, triple y jonrón en el mismo juego.
--
-- GRANO: juego-jugador. Universo 292.948, medido 2026-08-03.
-- Medido: 20 veces, 16 jugadores. Rareza 457.
--
-- El sencillo NO está en `retroDaily` como columna: se deduce restando extrabases a los hits, que es
-- la única forma que hay. `B_H` incluye los cuatro tipos.
-- =====================================================================================
WITH d AS (
    SELECT r.PLAYER_ID, r.GAME_ID, r.GAME_DT, r.SEASON, r.TEAM_ID, r.OPPONENT_ID, r.HOME_FL,
           r.B_H, r.B_2B, r.B_3B, r.B_HR, r.B_RBI, 'R' AS gt
    FROM   dbo.retroDailyReg r
    INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
    UNION ALL
    SELECT p.PLAYER_ID, p.GAME_ID, p.GAME_DT, p.SEASON, p.TEAM_ID, p.OPPONENT_ID, p.HOME_FL,
           p.B_H, p.B_2B, p.B_3B, p.B_HR, p.B_RBI, 'P'
    FROM   dbo.retroDailyPost p
    INNER JOIN dbo.dglMaster m2 ON m2.retroID = p.PLAYER_ID
),
-- El WPA del jugador en ese juego, para el bono de impacto. Sale de `r24Events`, que ya lo trae
-- calculado por turno — ver docs/EFEMERIDES.md 2.1.
wpa AS (
    SELECT v.GAME_ID, v.BATTER_ID, SUM(v.WPA) AS wpa, MAX(v.LI) AS li
    FROM   dbo.r24Events v
    WHERE  v.BAT_EVENT_FL = 1
    GROUP BY v.GAME_ID, v.BATTER_ID
)
SELECT  'ciclo'                                   AS tipo,
        'bateador'                                AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        292948                                    AS universo,
        'Bateó para el ciclo contra {rival_nombre}, ante el abridor {oponente}: {detalle}.' AS plantilla,
        m.mlbID                                   AS mlb_id,
        m.nameList                                AS nombre,
        CAST(d.GAME_DT AS date)                   AS fecha,
        d.SEASON                                  AS temporada,
        d.GAME_ID                                 AS game_id,
        0                                         AS event_id,
        d.gt                                      AS game_type,
        d.TEAM_ID                                 AS equipo,
        d.OPPONENT_ID                             AS rival,
        d.HOME_FL                                 AS en_casa,
        1                                         AS signo,
        -- La magnitud de un ciclo no es «cuántos ciclos»: todos son uno. Lo que separa a unos de
        -- otros es lo que hizo ADEMÁS, así que se usan las bases alcanzadas del juego.
        (d.B_H - d.B_2B - d.B_3B - d.B_HR) + 2*d.B_2B + 3*d.B_3B + 4*d.B_HR AS magnitud,
        w.wpa                                     AS wpa_jugador,
        w.li                                      AS li_max,
        -- La concordancia se resuelve acá y no en el sitio, porque el CSV lleva el texto ya
        -- redactado. Salió en la primera corrida: «5 hits y 1 empujadas».
        CAST(d.B_H AS varchar(2)) + ' hits y ' + CAST(d.B_RBI AS varchar(2))
            + CASE WHEN d.B_RBI = 1 THEN ' empujada' ELSE ' empujadas' END AS detalle,
        -- El contexto: los nombres salen del preludio `_00_comun.sql`, que resuelve equipos y
        -- peloteros una sola vez para toda la corrida.
        eq.nombre                                 AS equipo_nombre,
        ri.nombre                                 AS rival_nombre,
        -- El abridor RIVAL: si el dominicano bateaba en casa (`HOME_FL = 1`), el rival abrió de
        -- visita, y al revés. Es la vuelta que se olvida y deja al jugador enfrentándose a su propio
        -- compañero de equipo.
        COALESCE(op.nombre, '')                   AS oponente
FROM    d
INNER JOIN dbo.dglMaster m ON m.retroID = d.PLAYER_ID
LEFT  JOIN wpa w  ON w.GAME_ID = d.GAME_ID AND w.BATTER_ID = d.PLAYER_ID
LEFT  JOIN #equipos   eq ON eq.codigo = d.TEAM_ID     AND d.GAME_DT BETWEEN eq.desde AND eq.hasta
LEFT  JOIN #equipos   ri ON ri.codigo = d.OPPONENT_ID AND d.GAME_DT BETWEEN ri.desde AND ri.hasta
LEFT  JOIN #abridores ab ON ab.game_id = d.GAME_ID
LEFT  JOIN #nombres   op ON op.retro_id = CASE WHEN d.HOME_FL = 1 THEN ab.abridor_visita ELSE ab.abridor_casa END
WHERE   d.B_2B >= 1
  AND   d.B_3B >= 1
  AND   d.B_HR >= 1
  AND   (d.B_H - d.B_2B - d.B_3B - d.B_HR) >= 1;
