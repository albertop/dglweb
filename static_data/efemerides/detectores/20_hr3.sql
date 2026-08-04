-- =====================================================================================
-- Tres jonrones en un juego. Medido: 64 veces, 36 jugadores. Rareza 402.
--
-- El umbral se queda en 3 y NO hay detector de 4: ningún dominicano ha bateado cuatro en un juego.
-- El día que pase, la magnitud lo sube solo al tope de su tipo — ver docs/EFEMERIDES.md 5.1.6.
--
-- Sale de `#juegos`, que arma el preludio `_00_comun.sql`: la línea de cada dominicano en cada
-- juego, con equipo, rival, abridor y WPA ya resueltos. Ver docs/EFEMERIDES.md 8.0.
-- =====================================================================================
SELECT  'hr3'                                   AS tipo,
        'bateador'                                    AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        292948                                 AS universo,
        'Conectó {magnitud} jonrones contra {rival_nombre}, ante el abridor {oponente}: {detalle}.'                              AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                    AS signo,
        j.B_HR                                 AS magnitud,
        j.wpa_bat                                    AS wpa_jugador,
        j.li_max,
        CAST(j.B_RBI AS varchar(2)) + CASE WHEN j.B_RBI = 1 THEN ' empujada' ELSE ' empujadas' END + ' y ' + CAST(j.B_TB AS varchar(2)) + ' bases'                                  AS detalle,
        j.equipo_nombre, j.rival_nombre, j.oponente
FROM    #juegos j
WHERE   j.B_HR >= 3;
