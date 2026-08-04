-- =====================================================================================
-- Quince o más ponches. Medido: 16 veces, SEIS lanzadores. Rareza 468.
--
-- Es de los casos donde los dos conteos más se separan: 16 juegos pero solo 6 lanzadores, o sea 2,67
-- cada uno. Por eso el texto dice «uno de los 6», no «uno de los 16» — ver docs/EFEMERIDES.md 3.3.
--
-- Sale de `#juegos`, que arma el preludio `_00_comun.sql`: la línea de cada dominicano en cada
-- juego, con equipo, rival, abridor y WPA ya resueltos. Ver docs/EFEMERIDES.md 8.0.
-- =====================================================================================
SELECT  'k15'                                   AS tipo,
        'lanzador'                                    AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        292948                                 AS universo,
        'Ponchó a {magnitud} contra {rival_nombre}: {detalle}.'                              AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                    AS signo,
        j.P_SO                                 AS magnitud,
        j.wpa_pit                                    AS wpa_jugador,
        j.li_max,
        CAST(j.P_OUT / 3 AS varchar(3)) + CASE j.P_OUT % 3 WHEN 1 THEN '.1' WHEN 2 THEN '.2' ELSE '' END + ' entradas' + CASE WHEN j.P_ER = 0 THEN ' sin carreras limpias' WHEN j.P_ER = 1 THEN ' y 1 limpia' ELSE ' y ' + CAST(j.P_ER AS varchar(2)) + ' limpias' END                                  AS detalle,
        j.equipo_nombre, j.rival_nombre,
        -- SIN ABRIDOR RIVAL: ver el porqué en el preludio. Esto es una gesta de JUEGO COMPLETO.
        ''                                        AS oponente
FROM    #juegos j
WHERE   j.P_SO >= 15;
