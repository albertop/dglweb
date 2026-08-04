-- =====================================================================================
-- Cuatro o más dobles matanzas inducidas. Medido: 19 veces, 14 lanzadores. Rareza 460.
--
-- Es HAZAÑA, al reves que gidp3: inducir una doble matanza es salir de un lio con un lanzamiento.
-- El record dominicano son CINCO — Luis Perdomo, 2016-08-28, en juego completo de una limpia.
--
-- Sale de `#juegos` (preludio `_00_comun.sql`). Sin abridor rival: gesta de juego completo.
-- =====================================================================================
SELECT  'gidp_inducidos' AS tipo,
        'lanzador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        292948 AS universo,
        'Indujo {magnitud} dobles matanzas contra {rival_nombre}: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0 AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1 AS signo,
        j.P_GDP AS magnitud,
        j.wpa_pit AS wpa_jugador,
        j.li_max,
        CAST(j.P_OUT / 3 AS varchar(3)) + CASE j.P_OUT % 3 WHEN 1 THEN '.1' WHEN 2 THEN '.2' ELSE '' END + ' entradas' + CASE WHEN j.P_ER = 0 THEN ' sin carreras limpias' WHEN j.P_ER = 1 THEN ' y 1 limpia' ELSE ' y ' + CAST(j.P_ER AS varchar(2)) + ' limpias' END AS detalle,
        j.equipo_nombre, j.rival_nombre,
        '' AS oponente
FROM    #juegos j
WHERE   j.P_GDP >= 4;
