-- =====================================================================================
-- Dos o más triples. Medido: 75 veces, 47 jugadores. Rareza 395.
--
-- El umbral se corta donde deja de ser rutina, no donde se vuelve único: el único juego de TRES
-- triples —Rafael Furcal, 2002-04-21— entra por acá y la magnitud lo sube sola. Ver 5.1.2.
--
-- Sale de `#juegos`, que arma el preludio `_00_comun.sql`: la línea de cada dominicano en cada
-- juego, con equipo, rival, abridor y WPA ya resueltos. Ver docs/EFEMERIDES.md 8.0.
-- =====================================================================================
SELECT  'triples2'                                   AS tipo,
        'bateador'                                    AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        292948                                 AS universo,
        'Bateó {magnitud} triples contra {rival_nombre}: {detalle}.'                              AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                    AS signo,
        j.B_3B                                 AS magnitud,
        j.wpa_bat                                    AS wpa_jugador,
        j.li_max,
        CAST(j.B_H AS varchar(2)) + ' hits' + CASE WHEN j.B_RBI = 0 THEN '' WHEN j.B_RBI = 1 THEN ' y 1 empujada' ELSE ' y ' + CAST(j.B_RBI AS varchar(2)) + ' empujadas' END                                  AS detalle,
        j.equipo_nombre, j.rival_nombre,
        -- SIN ABRIDOR RIVAL: ver el porqué en el preludio. Esto es una gesta de JUEGO COMPLETO.
        ''                                        AS oponente
FROM    #juegos j
WHERE   j.B_3B >= 2;
