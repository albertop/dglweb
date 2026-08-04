-- =====================================================================================
-- El «casi no-hitter»: juego completo de un solo hit. Medido: 37 veces. Rareza 428.
--
-- Se pide P_H = 1 exacto y no <= 1: el cero ya es no_hitter, y con <= dispararían los dos sobre el
-- mismo juego para que la fusion los volviera a juntar. Mejor no crear el duplicado.
--
-- Sale de `#juegos` (preludio `_00_comun.sql`). Sin abridor rival: gesta de juego completo.
-- =====================================================================================
SELECT  'cg_1hit' AS tipo,
        'lanzador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        292948 AS universo,
        'Lanzó juego completo de UN SOLO HIT contra {rival_nombre}: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0 AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1 AS signo,
        j.P_SO AS magnitud,
        j.wpa_pit AS wpa_jugador,
        j.li_max,
        CAST(j.P_OUT / 3 AS varchar(3)) + CASE j.P_OUT % 3 WHEN 1 THEN '.1' WHEN 2 THEN '.2' ELSE '' END + ' entradas' + ' y ' + CAST(j.P_SO AS varchar(2)) + ' ponches' AS detalle,
        j.equipo_nombre, j.rival_nombre,
        '' AS oponente
FROM    #juegos j
WHERE   j.P_CG >= 1 AND j.P_H = 1;
