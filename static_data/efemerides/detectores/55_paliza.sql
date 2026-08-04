-- =====================================================================================
-- Diez hits y diez carreras permitidas. Medido: 19 veces, 17 lanzadores. Rareza 230.
--
-- Sale de `#juegos` (preludio `_00_comun.sql`). Sin abridor rival: gesta de juego completo.
-- =====================================================================================
SELECT  'paliza' AS tipo,
        'lanzador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        292948 AS universo,
        'Le cayeron encima los {rival_nombre}: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0 AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        -1 AS signo,
        j.P_R AS magnitud,
        NULL AS wpa_jugador,
        j.li_max,
        CAST(j.P_H AS varchar(2)) + ' hits y ' + CAST(j.P_R AS varchar(2)) + ' carreras en ' + CAST(j.P_OUT / 3 AS varchar(3)) + CASE j.P_OUT % 3 WHEN 1 THEN '.1' WHEN 2 THEN '.2' ELSE '' END + ' entradas' AS detalle,
        j.equipo_nombre, j.rival_nombre,
        '' AS oponente
FROM    #juegos j
WHERE   j.P_H >= 10 AND j.P_R >= 10;
