-- =====================================================================================
-- Cinco o más hits. Medido: 153 veces, 93 jugadores. Rareza 360.
--
-- Se revisó porque 153 parecía mucho; medido por temporada son 1,32 — nada. Y no tiene punto
-- intermedio: subirlo a 6 lo dejaría en 7 hechos. Ver docs/EFEMERIDES.md 5.1.0.
--
-- Sale de `#juegos`, que arma el preludio `_00_comun.sql`: la línea de cada dominicano en cada
-- juego, con equipo, rival, abridor y WPA ya resueltos. Ver docs/EFEMERIDES.md 8.0.
-- =====================================================================================
SELECT  'hits5'                                   AS tipo,
        'bateador'                                    AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        292948                                 AS universo,
        'Disparó {magnitud} hits contra {rival_nombre}, ante el abridor {oponente}: {detalle}.'                              AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                    AS signo,
        j.B_H                                 AS magnitud,
        j.wpa_bat                                    AS wpa_jugador,
        j.li_max,
        CAST(j.B_AB AS varchar(2)) + ' turnos, ' + CAST(j.B_RBI AS varchar(2)) + CASE WHEN j.B_RBI = 1 THEN ' empujada' ELSE ' empujadas' END                                  AS detalle,
        j.equipo_nombre, j.rival_nombre, j.oponente
FROM    #juegos j
WHERE   j.B_H >= 5;
