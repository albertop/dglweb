-- =====================================================================================
-- Blanqueada en juego completo. Medido: 271 veces. Rareza 333.
--
-- Es de los tres que más volumen mueven (2,34 por temporada). Entra igual: una blanqueada completa
-- es una gesta reconocible, y su puntaje bajo la deja donde debe estar.
--
-- Sale de `#juegos`, que arma el preludio `_00_comun.sql`: la línea de cada dominicano en cada
-- juego, con equipo, rival, abridor y WPA ya resueltos. Ver docs/EFEMERIDES.md 8.0.
-- =====================================================================================
SELECT  'blanqueada'                                   AS tipo,
        'lanzador'                                    AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        292948                                 AS universo,
        'Blanqueó a {rival_nombre} en juego completo: {detalle}.'                              AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                    AS signo,
        j.P_SO                                 AS magnitud,
        j.wpa_pit                                    AS wpa_jugador,
        j.li_max,
        CAST(j.P_H AS varchar(2)) + CASE WHEN j.P_H = 1 THEN ' hit' ELSE ' hits' END + ' y ' + CAST(j.P_SO AS varchar(2)) + CASE WHEN j.P_SO = 1 THEN ' ponche' ELSE ' ponches' END                                  AS detalle,
        j.equipo_nombre, j.rival_nombre,
        -- SIN ABRIDOR RIVAL: ver el porqué en el preludio. Esto es una gesta de JUEGO COMPLETO.
        ''                                        AS oponente
FROM    #juegos j
WHERE   j.P_SHO >= 1;
