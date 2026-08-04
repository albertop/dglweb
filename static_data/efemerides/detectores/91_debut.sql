-- =====================================================================================
-- El aniversario del debut.
--
-- `situar = 1`, al reves que el cumpleanos: aca la frase SI vale. «El primer dominicano en llegar a
-- Grandes Ligas» es de las mejores efemerides que hay, y sale sola del campo `orden`.
--
-- GRANO: persona. La rareza no significa nada acá —todos nacen, todos debutan— así que el
-- puntaje lo pone la MAGNITUD: los juegos de su carrera. Eso hace que el de Pedro Martínez
-- pese más que el de alguien con tres juegos, sin mantener ninguna lista de «importantes».
-- Ver docs/EFEMERIDES.md 4.6.
-- =====================================================================================
SELECT  'debut' AS tipo,
        'persona' AS rol,
        'completa' AS cobertura,
        2 AS situar,
        984 AS universo,
        'Debutó en Grandes Ligas hace {detalle}.' AS plantilla,
        m.mlbID AS mlb_id,
        m.nameList AS nombre,
        DATEFROMPARTS(YEAR(GETDATE()), MONTH(m.debutDate), DAY(m.debutDate)) AS fecha,
        YEAR(m.debutDate) AS temporada,
        '' AS game_id, 0 AS event_id, '-' AS game_type,
        '' AS equipo, '' AS rival, 0 AS en_casa,
        1 AS signo,
        COALESCE((SELECT COUNT(1) FROM dbo.retroDailyReg r WHERE r.PLAYER_ID = m.retroID), 0) AS magnitud,
        NULL AS wpa_jugador, NULL AS li_max,
        CAST(YEAR(GETDATE()) - YEAR(m.debutDate) AS varchar(3)) + ' años' AS detalle,
        '' AS equipo_nombre, '' AS rival_nombre, '' AS oponente
FROM    dbo.dglMaster m
WHERE   m.debutDate IS NOT NULL;
