-- =====================================================================================
-- El juego perfecto. Medido: 1 vez — Domingo Germán, 2023-06-28. Rareza 600, el tope.
--
-- POR QUÉ LLEVA DETECTOR PROPIO Y NO ES «UN NO-HITTER CON MÁS MAGNITUD». El patrón general dice lo
-- contrario —no un detector por escalón— y vale para tres triples contra dos: son la MISMA gesta,
-- más grande. El perfecto no: tiene nombre propio y una definición que no es «un no-hitter mejor».
-- La primera corrida del motor lo demostró con números — ver el comentario de 40_no_hitter.sql.
--
-- Sale de `#juegos`, que arma el preludio `_00_comun.sql`: la línea de cada dominicano en cada
-- juego, con equipo, rival, abridor y WPA ya resueltos. Ver docs/EFEMERIDES.md 8.0.
-- =====================================================================================
SELECT  'perfecto'                                   AS tipo,
        'lanzador'                                    AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        292948                                 AS universo,
        'Lanzó un JUEGO PERFECTO contra {rival_nombre}: 27 bateadores, 27 outs, {detalle}.'                              AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                    AS signo,
        j.P_SO                                 AS magnitud,
        j.wpa_pit                                    AS wpa_jugador,
        j.li_max,
        CAST(j.P_SO AS varchar(2)) + ' ponches'                                  AS detalle,
        j.equipo_nombre, j.rival_nombre,
        -- SIN ABRIDOR RIVAL: ver el porqué en el preludio. Esto es una gesta de JUEGO COMPLETO.
        ''                                        AS oponente
FROM    #juegos j
WHERE   j.P_H = 0 AND j.P_BB = 0 AND j.P_HP = 0 AND j.P_OUT >= 27;
