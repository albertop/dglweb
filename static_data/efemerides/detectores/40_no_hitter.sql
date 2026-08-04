-- =====================================================================================
-- Juego sin hits, nueve entradas o más. Medido: 10 veces, 10 lanzadores — acá los dos conteos
-- coinciden, cosa que casi no pasa. Rareza 490.
--
-- `P_OUT >= 27` NO ES OPCIONAL: `P_CG` marca «juego completo» e incluye los acortados por lluvia.
--
-- EL JUEGO PERFECTO TIENE DETECTOR PROPIO (`41_perfecto.sql`). Metido acá sacaba 767 y quedaba
-- DEBAJO del no-hitter de Ervin Santana (774), porque el de Santana fue cerrado y el de Germán un
-- 11-0. No se excluye: los dos disparan y la fusión se queda con el de más puntaje.
--
-- Sale de `#juegos`, que arma el preludio `_00_comun.sql`: la línea de cada dominicano en cada
-- juego, con equipo, rival, abridor y WPA ya resueltos. Ver docs/EFEMERIDES.md 8.0.
-- =====================================================================================
SELECT  'no_hitter'                                   AS tipo,
        'lanzador'                                    AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        292948                                 AS universo,
        'Lanzó un juego SIN HITS contra {rival_nombre}: {detalle}.'                              AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                    AS signo,
        27 - (j.P_BB + j.P_HP)                                 AS magnitud,
        j.wpa_pit                                    AS wpa_jugador,
        j.li_max,
        CAST(j.P_SO AS varchar(2)) + CASE WHEN j.P_SO = 1 THEN ' ponche' ELSE ' ponches' END + ' y ' + CAST(j.P_BB + j.P_HP AS varchar(2)) + CASE WHEN (j.P_BB + j.P_HP) = 1 THEN ' hombre a base' ELSE ' hombres a base' END                                  AS detalle,
        j.equipo_nombre, j.rival_nombre, j.oponente
FROM    #juegos j
WHERE   j.P_H = 0 AND j.P_OUT >= 27;
