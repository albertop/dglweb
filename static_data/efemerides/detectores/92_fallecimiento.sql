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
        -- «Falleció a los X años de edad» y NO «Murió hace X años» (dueño, 2026-08-03). La edad al
        -- morir dice algo del hombre; los años transcurridos solo dicen en qué año estamos, y encima
        -- envejecen solos: el mismo texto cambia cada 1 de enero sin que pase nada.
        --
        -- SIN NATALICIO NO SE DICE LA EDAD. La edad sale de restar el nacimiento, y para los de
        -- `#sin_natalicio` esa fecha es un relleno: daría una cifra falsa con toda la seguridad de
        -- una cifra exacta. El aniversario de la muerte sí se publica —esa fecha se conoce— y lo
        -- único que se calla es lo que no sabemos.
        CASE WHEN m.retroID IN (SELECT retro_id FROM #sin_natalicio)
             THEN 'Falleció en {temporada}.'
             ELSE 'Falleció en {temporada}, a los {detalle} años de edad.' END AS plantilla,
        m.mlbID AS mlb_id,
        m.nameList AS nombre,
        DATEFROMPARTS(YEAR(GETDATE()), MONTH(m.deathDate), DAY(m.deathDate)) AS fecha,
        YEAR(m.deathDate) AS temporada,
        '' AS game_id, 0 AS event_id, '-' AS game_type,
        '' AS equipo, '' AS rival, 0 AS en_casa,
        1 AS signo,
        COALESCE((SELECT COUNT(1) FROM dbo.retroDailyReg r WHERE r.PLAYER_ID = m.retroID), 0) AS magnitud,
        NULL AS wpa_jugador, NULL AS li_max,
        -- LA EDAD AL MORIR, Y NO BASTA RESTAR LOS AÑOS. `DATEDIFF(YEAR, ...)` en SQL Server cuenta
        -- fronteras de año calendario, no cumpleaños: de un nacido el 30 de diciembre que muere el 2
        -- de enero diría «1 año». Hay que descontar uno cuando el cumpleaños todavía no había
        -- llegado ese año.
        CAST(
            DATEDIFF(YEAR, m.birthDate, m.deathDate)
            - CASE WHEN MONTH(m.deathDate) < MONTH(m.birthDate)
                     OR (MONTH(m.deathDate) = MONTH(m.birthDate) AND DAY(m.deathDate) < DAY(m.birthDate))
                   THEN 1 ELSE 0 END
        AS varchar(3)) AS detalle,
        '' AS equipo_nombre, '' AS rival_nombre, '' AS oponente
FROM    dbo.dglMaster m
WHERE   m.deathDate IS NOT NULL;

-- =====================================================================================
-- LA LISTA — para cuando pregunten «¿quiénes son esos?»
--
-- Se pega tal cual y corre sola. Son 61. El descuento del `CASE` no es adorno: sin él la edad sale mal en 31 de los 61.
-- =====================================================================================
/*
SELECT  m.nameList AS jugador,
        m.mlbID    AS mlb_id,
        CAST(m.deathDate AS date) AS fallecimiento,
        CAST(m.birthDate AS date) AS nacimiento,
        DATEDIFF(YEAR, m.birthDate, m.deathDate)
          - CASE WHEN MONTH(m.deathDate) < MONTH(m.birthDate)
                   OR (MONTH(m.deathDate) = MONTH(m.birthDate) AND DAY(m.deathDate) < DAY(m.birthDate))
                 THEN 1 ELSE 0 END AS edad_al_morir,
        m.yearDomHof              AS salon_dominicano
FROM    dbo.dglMaster m
WHERE   m.deathDate IS NOT NULL
ORDER BY MONTH(m.deathDate), DAY(m.deathDate);
*/
