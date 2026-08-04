-- =====================================================================================
-- Siete o más empujadas. Medido: 43 veces, 29 jugadores. Rareza 421.
--
-- El umbral subió de 6 a 7 por decisión del dueño, y la diferencia es grande: con 6 eran 165 hechos
-- y rareza 357. El tope dominicano son DIEZ empujadas — Alex Rodríguez, 2005-04-26.
--
-- Sale de `#juegos`, que arma el preludio `_00_comun.sql`: la línea de cada dominicano en cada
-- juego, con equipo, rival, abridor y WPA ya resueltos. Ver docs/EFEMERIDES.md 8.0.
-- =====================================================================================
SELECT  'rbi7'                                   AS tipo,
        'bateador'                                    AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        292948                                 AS universo,
        'Empujó {magnitud} carreras contra {rival_nombre}, ante el abridor {oponente}: {detalle}.'                              AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                    AS signo,
        j.B_RBI                                 AS magnitud,
        j.wpa_bat                                    AS wpa_jugador,
        j.li_max,
        CAST(j.B_H AS varchar(2)) + ' hits y ' + CAST(j.B_HR AS varchar(2)) + CASE WHEN j.B_HR = 1 THEN ' jonrón' ELSE ' jonrones' END                                  AS detalle,
        j.equipo_nombre, j.rival_nombre, j.oponente
FROM    #juegos j
WHERE   j.B_RBI >= 7;
