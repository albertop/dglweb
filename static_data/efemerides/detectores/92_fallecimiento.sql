-- =====================================================================================
-- El aniversario del fallecimiento. Medido: 61 dominicanos, 1943-2025, en 55 dias del calendario.
-- Veinticuatro de ellos estan en el Salon de la Fama dominicano.
--
-- Es la contraparte exacta de `90_cumpleanos.sql`: los 61 que salen aca son justo los 61 que aquel
-- excluye. Felicitar a un muerto por su cumpleanos es el tipo de error que un sistema automatico
-- comete y una persona no.
--
-- `situar = 0`: «uno de los N dominicanos que lo ha logrado» no se le dice a una muerte.
--
-- GRANO: persona. La rareza no significa nada acá —todos nacen, todos debutan— así que el
-- puntaje lo pone la MAGNITUD: los juegos de su carrera. Eso hace que el de Pedro Martínez
-- pese más que el de alguien con tres juegos, sin mantener ninguna lista de «importantes».
-- Ver docs/EFEMERIDES.md 4.6.
-- =====================================================================================
SELECT  'fallecimiento' AS tipo,
        'persona' AS rol,
        'completa' AS cobertura,
        0 AS situar,
        984 AS universo,
        'Murió hace {detalle}.' AS plantilla,
        m.mlbID AS mlb_id,
        m.nameList AS nombre,
        DATEFROMPARTS(YEAR(GETDATE()), MONTH(m.deathDate), DAY(m.deathDate)) AS fecha,
        YEAR(m.deathDate) AS temporada,
        '' AS game_id, 0 AS event_id, '-' AS game_type,
        '' AS equipo, '' AS rival, 0 AS en_casa,
        1 AS signo,
        COALESCE((SELECT COUNT(1) FROM dbo.retroDailyReg r WHERE r.PLAYER_ID = m.retroID), 0) AS magnitud,
        NULL AS wpa_jugador, NULL AS li_max,
        CAST(YEAR(GETDATE()) - YEAR(m.deathDate) AS varchar(3)) + ' años' AS detalle,
        '' AS equipo_nombre, '' AS rival_nombre, '' AS oponente
FROM    dbo.dglMaster m
WHERE   m.deathDate IS NOT NULL;
