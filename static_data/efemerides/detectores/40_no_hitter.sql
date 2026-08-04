-- =====================================================================================
-- El juego sin hits: nueve entradas o más sin permitir un solo indiscutible.
--
-- GRANO: juego-jugador. Universo 292.948.
-- Medido: 10 veces, 10 lanzadores distintos — acá los dos conteos coinciden, cosa que no pasa en
-- casi ningún otro detector. Rareza 490.
--
-- `P_OUT >= 27` NO ES OPCIONAL, y es la misma trampa que en `cg90`: `P_CG` marca «juego completo» e
-- incluye los acortados por lluvia. Sin exigir las nueve entradas entrarían juegos de seis.
--
-- EL JUEGO PERFECTO TIENE SU PROPIO DETECTOR (`41_perfecto.sql`), y no por gusto: metido acá, la
-- primera corrida del motor lo dejó en 767 puntos, DEBAJO del no-hitter de Ervin Santana (774),
-- porque el de Santana fue un juego cerrado y el de Germán un 11-0. No se excluye de esta consulta:
-- los dos disparan y la fusión se queda con el de más puntaje.
-- =====================================================================================
WITH d AS (
    SELECT r.PLAYER_ID, r.GAME_ID, r.GAME_DT, r.SEASON, r.TEAM_ID, r.OPPONENT_ID, r.HOME_FL,
           r.P_OUT, r.P_H, r.P_BB, r.P_HP, r.P_SO, 'R' AS gt
    FROM   dbo.retroDailyReg r
    INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
    UNION ALL
    SELECT p.PLAYER_ID, p.GAME_ID, p.GAME_DT, p.SEASON, p.TEAM_ID, p.OPPONENT_ID, p.HOME_FL,
           p.P_OUT, p.P_H, p.P_BB, p.P_HP, p.P_SO, 'P'
    FROM   dbo.retroDailyPost p
    INNER JOIN dbo.dglMaster m2 ON m2.retroID = p.PLAYER_ID
),
-- El WPA del LANZADOR es el del bateador con el signo cambiado: lo que el bateador le quita a su
-- equipo, el lanzador se lo da al suyo.
wpa AS (
    SELECT v.GAME_ID, v.PITCHER_ID, -SUM(v.WPA) AS wpa, MAX(v.LI) AS li
    FROM   dbo.r24Events v
    WHERE  v.BAT_EVENT_FL = 1
    GROUP BY v.GAME_ID, v.PITCHER_ID
)
SELECT  'no_hitter'                               AS tipo,
        'lanzador'                                AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        292948                                    AS universo,
        'Lanzó un juego SIN HITS contra {rival_nombre}: {detalle}.' AS plantilla,
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
        -- Menos hombres a base, mayor magnitud. El perfecto queda en 27 y sube solo al tope.
        27 - (d.P_BB + d.P_HP)                    AS magnitud,
        w.wpa                                     AS wpa_jugador,
        w.li                                      AS li_max,
        CAST(d.P_SO AS varchar(2)) + CASE WHEN d.P_SO = 1 THEN ' ponche' ELSE ' ponches' END
            + ' y ' + CAST(d.P_BB + d.P_HP AS varchar(2))
            + CASE WHEN (d.P_BB + d.P_HP) = 1 THEN ' hombre a base' ELSE ' hombres a base' END AS detalle,
        eq.nombre                                 AS equipo_nombre,
        ri.nombre                                 AS rival_nombre,
        ''                                        AS oponente
FROM    d
INNER JOIN dbo.dglMaster m ON m.retroID = d.PLAYER_ID
LEFT  JOIN wpa w      ON w.GAME_ID = d.GAME_ID AND w.PITCHER_ID = d.PLAYER_ID
LEFT  JOIN #equipos eq ON eq.codigo = d.TEAM_ID     AND d.GAME_DT BETWEEN eq.desde AND eq.hasta
LEFT  JOIN #equipos ri ON ri.codigo = d.OPPONENT_ID AND d.GAME_DT BETWEEN ri.desde AND ri.hasta
WHERE   d.P_H = 0
  AND   d.P_OUT >= 27;
