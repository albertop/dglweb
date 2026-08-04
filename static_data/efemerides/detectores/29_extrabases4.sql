-- =====================================================================================
-- Cuatro o más extrabases en un juego. Medido: 33 veces. Rareza 433.
--
-- Sale de `#juegos` (preludio `_00_comun.sql`). Sin abridor rival: gesta de juego completo.
-- =====================================================================================
SELECT  'extrabases4' AS tipo,
        'bateador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        292948 AS universo,
        'Conectó {magnitud} extrabases contra {rival_nombre}: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0 AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1 AS signo,
        (j.B_2B + j.B_3B + j.B_HR) AS magnitud,
        j.wpa_bat AS wpa_jugador,
        j.li_max,
        STUFF(CASE WHEN j.B_2B > 0 THEN ', ' + CAST(j.B_2B AS varchar(2)) + CASE WHEN j.B_2B = 1 THEN ' doble' ELSE ' dobles' END ELSE '' END + CASE WHEN j.B_3B > 0 THEN ', ' + CAST(j.B_3B AS varchar(2)) + CASE WHEN j.B_3B = 1 THEN ' triple' ELSE ' triples' END ELSE '' END + CASE WHEN j.B_HR > 0 THEN ', ' + CAST(j.B_HR AS varchar(2)) + CASE WHEN j.B_HR = 1 THEN ' jonrón' ELSE ' jonrones' END ELSE '' END, 1, 2, '') AS detalle,
        j.equipo_nombre, j.rival_nombre,
        '' AS oponente
FROM    #juegos j
WHERE   (j.B_2B + j.B_3B + j.B_HR) >= 4;
