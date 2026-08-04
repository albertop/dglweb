-- =====================================================================================
-- EL INNING INMACULADO: nueve lanzamientos, tres ponches, ni uno de más. La entrada perfecta.
--
-- Medido: OCHO dominicanos desde 2008.
--
--     2010  Rafael Soriano, 9no       2016  Juan Nicasio, 8vo
--     2011  Juan Pérez, inning 10     2017  Dellin Betances, 8vo
--     2013  Iván Nova, 8vo            2022  Enyel De los Santos, 7mo
--     2014  Carlos Contreras, 7mo
--     2015  Santiago Casilla, 9no
--
-- GRANO: medias entradas lanzadas por dominicanos EN LA VENTANA DE STATCAST (85.923), no las 162.797
-- de toda la historia. El universo tiene que medirse en la misma ventana que el numerador, o la
-- rareza sale inflada.
--
-- COBERTURA PARCIAL: 2008-2026, 19 de las 116 temporadas. El motor NO publica los totales
-- —«uno de los N dominicanos»— porque el número que tenemos es el de la ventana que vemos, no
-- el de la historia. Publicarlo como total sería mentir con precisión decimal.
-- =====================================================================================
SELECT  'inmaculado' AS tipo,
        'un inning inmaculado' AS gesta,
        'lanzador' AS rol,
        'parcial' AS cobertura,
        1 AS situar,
        85923 AS universo,
        'Lanzó un inning inmaculado contra {rival_nombre}: {detalle}.' AS plantilla,
        i.mlb_id, m.nameList AS nombre, i.fecha, p.temporada, p.game_id,
        0 AS event_id,
        p.game_type, p.equipo, p.rival, p.en_casa,
        1 AS signo,
        9 AS magnitud,
        NULL AS wpa_jugador, NULL AS li_max,
        'nueve lanzamientos, tres ponches, en el ' + CASE WHEN i.inning >= 10 THEN 'inning ' + CAST(i.inning AS varchar(2)) ELSE CASE i.inning WHEN 1 THEN '1er' WHEN 2 THEN '2do' WHEN 3 THEN '3er' WHEN 4 THEN '4to' WHEN 5 THEN '5to' WHEN 6 THEN '6to' WHEN 7 THEN '7mo' WHEN 8 THEN '8vo' ELSE '9no' END END AS detalle,
        p.equipo_nombre, p.rival_nombre,
        '' AS oponente
FROM    #sc_inning i
INNER JOIN dbo.dglMaster m ON m.mlbID = i.mlb_id
INNER JOIN #puente p ON p.mlb_id = i.mlb_id AND p.fecha = i.fecha
WHERE   i.lanzamientos = 9 AND i.ponches = 3;
