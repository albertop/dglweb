-- =====================================================================================
-- Seis o mas ponches. HOY DEVUELVE CERO: ningun dominicano lo ha hecho, y en toda la liga
-- solo ha pasado 8 veces en 116 anos.
--
-- Se escribe igual, por lo mismo que ciclo_natural: cuesta nada y empieza a producir el dia que
-- pase. Un detector vacio es una apuesta gratis.
--
-- Sale de `#juegos` (preludio `_00_comun.sql`). Sin abridor rival: gesta de juego completo.
-- =====================================================================================
SELECT  'sombrero_titanio' AS tipo,
        'bateador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        292948 AS universo,
        'Se puso el sombrero de TITANIO contra {rival_nombre}: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0 AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        -1 AS signo,
        j.B_SO AS magnitud,
        NULL AS wpa_jugador,
        j.li_max,
        'ponchado ' + CAST(j.B_SO AS varchar(2)) + ' veces' AS detalle,
        j.equipo_nombre, j.rival_nombre,
        '' AS oponente
FROM    #juegos j
WHERE   j.B_SO >= 6;
