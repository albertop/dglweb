-- =====================================================================================
-- Juego completo con 10+ ponches y cero limpias. Medido: 41 veces. Rareza 423.
--
-- Sale de `#juegos` (preludio `_00_comun.sql`). Sin abridor rival: gesta de juego completo.
-- =====================================================================================
SELECT  'cg_dominante' AS tipo,
        'lanzador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        292948 AS universo,
        'Lanzó juego completo con {magnitud} ponches y CERO carreras limpias contra {rival_nombre}: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0 AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1 AS signo,
        j.P_SO AS magnitud,
        j.wpa_pit AS wpa_jugador,
        j.li_max,
        CAST(j.P_H AS varchar(2)) + CASE WHEN j.P_H = 1 THEN ' hit permitido' ELSE ' hits permitidos' END AS detalle,
        j.equipo_nombre, j.rival_nombre,
        '' AS oponente
FROM    #juegos j
WHERE   j.P_CG >= 1 AND j.P_SO >= 10 AND j.P_ER = 0;
