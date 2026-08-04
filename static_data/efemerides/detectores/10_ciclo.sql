-- =====================================================================================
-- El ciclo: sencillo, doble, triple y jonrón en el mismo juego. Medido: 20 veces, 16 jugadores.
-- Rareza 457.
--
-- La MAGNITUD son las bases alcanzadas, no «cuántos ciclos»: todos son uno, y lo que separa a unos
-- de otros es lo que el jugador hizo ADEMÁS.
--
-- Sale de `#juegos`, que arma el preludio `_00_comun.sql`: la línea de cada dominicano en cada
-- juego, con equipo, rival, abridor y WPA ya resueltos. Ver docs/EFEMERIDES.md 8.0.
-- =====================================================================================
SELECT  'ciclo'                                   AS tipo,
        'bateador'                                    AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        292948                                 AS universo,
        'Bateó para el ciclo contra {rival_nombre}, ante el abridor {oponente}: {detalle}.'                              AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                    AS signo,
        j.B_TB                                 AS magnitud,
        j.wpa_bat                                    AS wpa_jugador,
        j.li_max,
        CAST(j.B_H AS varchar(2)) + ' hits y ' + CAST(j.B_RBI AS varchar(2)) + CASE WHEN j.B_RBI = 1 THEN ' empujada' ELSE ' empujadas' END                                  AS detalle,
        j.equipo_nombre, j.rival_nombre, j.oponente
FROM    #juegos j
WHERE   j.B_1B >= 1 AND j.B_2B >= 1 AND j.B_3B >= 1 AND j.B_HR >= 1;
