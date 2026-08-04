-- =====================================================================================
-- Cuatro o más anotadas. Medido: 233 veces. Rareza 340.
--
-- Sale de `#juegos` (preludio `_00_comun.sql`). Sin abridor rival: gesta de juego completo.
-- =====================================================================================
SELECT  'anotadas4' AS tipo,
        'bateador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        292948 AS universo,
        'Anotó {magnitud} carreras contra {rival_nombre}: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0 AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1 AS signo,
        j.B_R AS magnitud,
        j.wpa_bat AS wpa_jugador,
        j.li_max,
        CAST(j.B_H AS varchar(2)) + ' hits' + CASE WHEN j.B_BB = 0 THEN '' WHEN j.B_BB = 1 THEN ' y 1 boleto' ELSE ' y ' + CAST(j.B_BB AS varchar(2)) + ' boletos' END AS detalle,
        j.equipo_nombre, j.rival_nombre,
        '' AS oponente
FROM    #juegos j
WHERE   j.B_R >= 4;
