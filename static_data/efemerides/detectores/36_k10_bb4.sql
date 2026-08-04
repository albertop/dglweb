-- =====================================================================================
-- Dominante y salvaje a la vez: 10+ ponches con 4+ boletos. Medido: 73 veces. Rareza 395.
--
-- Sale de `#juegos` (preludio `_00_comun.sql`). Sin abridor rival: gesta de juego completo.
-- =====================================================================================
SELECT  'k10_bb4' AS tipo,
        'lanzador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        292948 AS universo,
        'Ponchó a {magnitud} contra {rival_nombre}, pero regaló {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0 AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1 AS signo,
        j.P_SO AS magnitud,
        j.wpa_pit AS wpa_jugador,
        j.li_max,
        CAST(j.P_BB AS varchar(2)) + CASE WHEN j.P_BB = 1 THEN ' boleto' ELSE ' boletos' END AS detalle,
        j.equipo_nombre, j.rival_nombre,
        '' AS oponente
FROM    #juegos j
WHERE   j.P_SO >= 10 AND j.P_BB >= 4;
