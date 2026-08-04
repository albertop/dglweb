-- =====================================================================================
-- Doce o más bases alcanzadas. Medido: 85 veces, 44 jugadores. Rareza 388.
--
-- HABÍA DOS DETECTORES DEL MISMO STAT —`bases10` y `bases12`— y eso contradice el patrón: un
-- umbral por gesta, y la magnitud se encarga del resto. Con 10 era el detector más ruidoso del
-- inventario (3,18 por temporada); con 12 queda en 0,73. Ver docs/EFEMERIDES.md 5.1.7.
--
-- Sale de `#juegos`, que arma el preludio `_00_comun.sql`: la línea de cada dominicano en cada
-- juego, con equipo, rival, abridor y WPA ya resueltos. Ver docs/EFEMERIDES.md 8.0.
-- =====================================================================================
SELECT  'bases12'                                   AS tipo,
        'bateador'                                    AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        292948                                 AS universo,
        'Alcanzó {magnitud} bases contra {rival_nombre}, ante el abridor {oponente}: {detalle}.'                              AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                    AS signo,
        j.B_TB                                 AS magnitud,
        j.wpa_bat                                    AS wpa_jugador,
        j.li_max,
        CAST(j.B_H AS varchar(2)) + ' hits, ' + CAST(j.B_HR AS varchar(2)) + CASE WHEN j.B_HR = 1 THEN ' jonrón' ELSE ' jonrones' END                                  AS detalle,
        j.equipo_nombre, j.rival_nombre, j.oponente
FROM    #juegos j
WHERE   j.B_TB >= 12;
