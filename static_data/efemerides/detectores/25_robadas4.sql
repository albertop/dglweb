-- =====================================================================================
-- Cuatro o más robadas. Medido: 14 veces, 12 jugadores. Rareza 474 — la más alta del grupo.
--
-- El máximo dominicano son CINCO, una sola vez: Willy Taveras, 2008-06-14. En 13 de los 14 no
-- atraparon a nadie, y por eso el detalle lo dice: «4 de 4» es mejor efeméride que «4 de 5».
--
-- Sale de `#juegos`, que arma el preludio `_00_comun.sql`: la línea de cada dominicano en cada
-- juego, con equipo, rival, abridor y WPA ya resueltos. Ver docs/EFEMERIDES.md 8.0.
-- =====================================================================================
SELECT  'robadas4'                                   AS tipo,
        'bateador'                                    AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        292948                                 AS universo,
        'Se robó {magnitud} bases contra {rival_nombre}: {detalle}.'                              AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                    AS signo,
        j.B_SB                                 AS magnitud,
        j.wpa_bat                                    AS wpa_jugador,
        j.li_max,
        CASE WHEN j.B_CS = 0 THEN 'sin que lo atraparan ni una vez' ELSE 'y lo atraparon ' + CAST(j.B_CS AS varchar(2)) + ' vez/veces' END                                  AS detalle,
        j.equipo_nombre, j.rival_nombre,
        -- SIN ABRIDOR RIVAL: ver el porqué en el preludio. Esto es una gesta de JUEGO COMPLETO.
        ''                                        AS oponente
FROM    #juegos j
WHERE   j.B_SB >= 4;
