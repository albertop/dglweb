-- =====================================================================================
-- Tres o mas pelotazos propinados. Medido: 25 veces, 20 lanzadores. Rareza 223.
--
-- Va en NEGATIVO: golpear a tres es un fallo de control. Con umbral 2 serian 411 juegos (3,54 por
-- temporada), demasiado corriente.
--
-- Sale de `#juegos` (preludio `_00_comun.sql`). Sin abridor rival: gesta de juego completo.
-- =====================================================================================
SELECT  'hbp_propinados' AS tipo,
        'lanzador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        292948 AS universo,
        'Golpeó a {magnitud} bateadores de {rival_nombre} en {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0 AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        -1 AS signo,
        j.P_HP AS magnitud,
        NULL AS wpa_jugador,
        j.li_max,
        CAST(j.P_OUT / 3 AS varchar(3)) + CASE j.P_OUT % 3 WHEN 1 THEN '.1' WHEN 2 THEN '.2' ELSE '' END + ' entradas' AS detalle,
        j.equipo_nombre, j.rival_nombre,
        '' AS oponente
FROM    #juegos j
WHERE   j.P_HP >= 3;
