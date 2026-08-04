-- =====================================================================================
-- Dos o mas pelotazos recibidos. Medido: 120 veces, 67 jugadores. Rareza 372.
--
-- VA EN POSITIVO, y es un juicio: al bateador no le pasa por culpa suya. Los propinados van en
-- negativo, que es la contraria. El tope dominicano son TRES, una sola vez.
--
-- Sale de `#juegos` (preludio `_00_comun.sql`). Sin abridor rival: gesta de juego completo.
-- =====================================================================================
SELECT  'hbp_recibidos' AS tipo,
        'bateador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        292948 AS universo,
        'Recibió {magnitud} pelotazos contra {rival_nombre}: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0 AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1 AS signo,
        j.B_HP AS magnitud,
        j.wpa_bat AS wpa_jugador,
        j.li_max,
        'llegó a base ' + CAST(j.B_HP + j.B_H + j.B_BB AS varchar(2)) + ' veces' AS detalle,
        j.equipo_nombre, j.rival_nombre,
        '' AS oponente
FROM    #juegos j
WHERE   j.B_HP >= 2;
