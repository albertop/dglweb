-- =====================================================================================
-- El juego perfecto: 27 outs, ni un hombre a base.
--
-- GRANO: juego-jugador. Universo 292.948.
-- Medido: 1 vez. Domingo Germán, 2023-06-28. Rareza 600 — el tope.
--
-- POR QUÉ LLEVA DETECTOR PROPIO Y NO ES «UN NO-HITTER CON MÁS MAGNITUD».
--
-- El patrón general del inventario (5.1.2) dice lo contrario: no se crea un detector para cada
-- escalón, la magnitud sube sola al que se pasa de la raya. Vale para tres triples contra dos, o
-- para seis hits contra cinco — son la MISMA gesta, más grande.
--
-- El perfecto no. Tiene nombre propio, libro de récords propio y una definición que no es «un
-- no-hitter mejor»: es no permitir NADA. Y la primera corrida del motor lo demostró con números —
-- dentro de `no_hitter`, el perfecto de Germán sacaba 767 y quedaba DEBAJO del no-hitter de Ervin
-- Santana (774), porque el de Santana fue un juego cerrado y el de Germán un 11-0. El bono de
-- impacto, que en todo lo demás hace bien su trabajo, hundía la gesta más rara del béisbol.
--
-- Con detector propio, la rareza (n=1 -> 600) lo pone donde va y el impacto solo desempata.
--
-- NO HACE FALTA EXCLUIRLO DE `40_no_hitter.sql`: los dos disparan sobre el mismo juego y la fusión
-- (sección 7) se queda con el de mayor puntaje —este— y anexa `no_hitter` como etiqueta.
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
wpa AS (
    SELECT v.GAME_ID, v.PITCHER_ID, -SUM(v.WPA) AS wpa, MAX(v.LI) AS li
    FROM   dbo.r24Events v
    WHERE  v.BAT_EVENT_FL = 1
    GROUP BY v.GAME_ID, v.PITCHER_ID
)
SELECT  'perfecto'                                AS tipo,
        'lanzador'                                AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        292948                                    AS universo,
        'Lanzó un JUEGO PERFECTO contra {rival_nombre}: 27 bateadores, 27 outs, {detalle}.' AS plantilla,
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
        d.P_SO                                    AS magnitud,
        w.wpa                                     AS wpa_jugador,
        w.li                                      AS li_max,
        CAST(d.P_SO AS varchar(2)) + ' ponches'   AS detalle,
        eq.nombre                                 AS equipo_nombre,
        ri.nombre                                 AS rival_nombre,
        ''                                        AS oponente
FROM    d
INNER JOIN dbo.dglMaster m ON m.retroID = d.PLAYER_ID
LEFT  JOIN wpa w      ON w.GAME_ID = d.GAME_ID AND w.PITCHER_ID = d.PLAYER_ID
LEFT  JOIN #equipos eq ON eq.codigo = d.TEAM_ID     AND d.GAME_DT BETWEEN eq.desde AND eq.hasta
LEFT  JOIN #equipos ri ON ri.codigo = d.OPPONENT_ID AND d.GAME_DT BETWEEN ri.desde AND ri.hasta
WHERE   d.P_H  = 0
  AND   d.P_BB = 0
  AND   d.P_HP = 0
  AND   d.P_OUT >= 27;
