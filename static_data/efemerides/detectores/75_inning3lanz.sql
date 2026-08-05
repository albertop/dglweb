-- =====================================================================================
-- TRES LANZAMIENTOS, TRES OUTS. El opuesto exacto del inning inmaculado: aquel es la entrada más
-- dominante posible, esta es la más eficiente.
--
-- Medido: ONCE dominicanos desde 2008.
--
-- LA MAGNITUD VA AL REVÉS —`9 - lanzamientos`— por lo mismo que en cg90: acá menos es más. Con tres
-- lanzamientos no hay margen para menos, así que todas empatan; queda por si algún día Retrosheet
-- corrige un conteo.
--
-- COBERTURA PARCIAL: 2008-2026, 19 de las 116 temporadas. El motor NO publica los totales
-- —«uno de los N dominicanos»— porque el número que tenemos es el de la ventana que vemos, no
-- el de la historia. Publicarlo como total sería mentir con precisión decimal.
-- =====================================================================================
SELECT  'inning3lanz' AS tipo,
        'una entrada de tres lanzamientos' AS gesta,
        '' AS participantes,
        'lanzador' AS rol,
        'parcial' AS cobertura,
        1 AS situar,
        85923 AS universo,
        'Retiró el inning con tres lanzamientos contra {rival_nombre}: {detalle}.' AS plantilla,
        i.mlb_id, m.nameList AS nombre, i.fecha, p.temporada, p.game_id,
        0 AS event_id,
        p.game_type, p.equipo, p.rival, p.en_casa,
        1 AS signo,
        (9 - i.lanzamientos) AS magnitud,
        NULL AS wpa_jugador, NULL AS li_max,
        'tres lanzamientos, tres outs, en el ' + CASE WHEN i.inning >= 10 THEN 'inning ' + CAST(i.inning AS varchar(2)) ELSE CASE i.inning WHEN 1 THEN '1er' WHEN 2 THEN '2do' WHEN 3 THEN '3er' WHEN 4 THEN '4to' WHEN 5 THEN '5to' WHEN 6 THEN '6to' WHEN 7 THEN '7mo' WHEN 8 THEN '8vo' ELSE '9no' END + ' inning' END AS detalle,
        p.equipo_nombre, p.rival_nombre,
        '' AS oponente
FROM    #sc_inning i
INNER JOIN dbo.dglMaster m ON m.mlbID = i.mlb_id
INNER JOIN #puente p ON p.mlb_id = i.mlb_id AND p.fecha = i.fecha
WHERE   i.lanzamientos = 3 AND i.turnos = 3;
