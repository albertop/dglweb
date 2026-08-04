-- =====================================================================================
-- Tres o más dobles. Medido: 136 veces, 80 jugadores. Rareza 366.
--
-- NO lo cubría `extrabases4`: ese suma dobles, triples y jonrones, así que un juego de tres dobles
-- y nada más se le escapaba — son tres extrabases, no cuatro.
--
-- Sale de `#juegos`, que arma el preludio `_00_comun.sql`: la línea de cada dominicano en cada
-- juego, con equipo, rival, abridor y WPA ya resueltos. Ver docs/EFEMERIDES.md 8.0.
-- =====================================================================================
SELECT  'dobles3'                                   AS tipo,
        'bateador'                                    AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        292948                                 AS universo,
        'Bateó {magnitud} dobles contra {rival_nombre}: {detalle}.'                              AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                    AS signo,
        j.B_2B                                 AS magnitud,
        j.wpa_bat                                    AS wpa_jugador,
        j.li_max,
        CAST(j.B_H AS varchar(2)) + ' hits en ' + CAST(j.B_AB AS varchar(2)) + ' turnos'                                  AS detalle,
        j.equipo_nombre, j.rival_nombre,
        -- SIN ABRIDOR RIVAL: ver el porqué en el preludio. Esto es una gesta de JUEGO COMPLETO.
        ''                                        AS oponente
FROM    #juegos j
WHERE   j.B_2B >= 3;
