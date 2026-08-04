-- =====================================================================================
-- Atrapado robando tres veces. Medido: UNA vez — Luis Polonia, 1993-05-24, sin robarse
-- ninguna. Rareza 300, el tope de la escala negativa.
--
-- El umbral se puso en 3 y no en 4 —que fue lo pedido— porque con 4 el detector nacia vacio: ningun
-- dominicano lo ha hecho y en toda la liga paso UNA vez. Ver docs/EFEMERIDES.md 5.1.5.
--
-- El mismo Polonia aparece dos veces en robadas4. Ladron y victima.
--
-- Sale de `#juegos` (preludio `_00_comun.sql`). Sin abridor rival: gesta de juego completo.
-- =====================================================================================
SELECT  'cs3' AS tipo,
        'bateador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        292948 AS universo,
        'Lo atraparon robando {magnitud} veces contra {rival_nombre}: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0 AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        -1 AS signo,
        j.B_CS AS magnitud,
        NULL AS wpa_jugador,
        j.li_max,
        CASE WHEN j.B_SB = 0 THEN 'sin robarse ninguna' ELSE 'aunque se robo ' + CAST(j.B_SB AS varchar(2)) END AS detalle,
        j.equipo_nombre, j.rival_nombre,
        '' AS oponente
FROM    #juegos j
WHERE   j.B_CS >= 3;
