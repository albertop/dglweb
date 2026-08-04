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
WHERE   m.debutDate IS NOT NULL
  -- EL 1 DE ENERO ES RELLENO, NO UNA FECHA. Cuando solo se conoce el AÑO del debut, `dglMaster`
  -- guarda el 1 de enero de ese año: Enrique Lantigua figura con `1935-01-01` y lo que se sabe es
  -- que fue en 1935 (dueño, 2026-08-04).
  --
  -- ACÁ SÍ SE PUEDE APAGAR POR REGLA, al revés que con los nacimientos. La temporada de Grandes
  -- Ligas va de marzo a octubre —medido, los 984 debuts caen entre marzo y octubre salvo estos
  -- cuatro— así que nadie debuta un 1 de enero y no hay ninguno legítimo que borrar. En cambio la
  -- gente sí NACE el 1 de enero, y por eso `90_cumpleanos.sql` necesita una lista a mano.
  --
  -- Y ESTA EFEMÉRIDE ES DE DÍA. Se consulta por «un día como hoy»: sin día no hay dónde ponerla, y
  -- publicarla el 1 de enero sería inventar la fecha. Son cuatro y todos de las Ligas Negras: Sijo
  -- Gómez y Néstor Lambertus (1929), Enrique Lantigua y Horacio Martínez (1935).
  AND   NOT (MONTH(m.debutDate) = 1 AND DAY(m.debutDate) = 1);

-- =====================================================================================
-- LA LISTA — para cuando pregunten «¿quiénes son esos?»
--
-- Se pega tal cual y corre sola. Los 984 del maestro debutaron. Para «el primero de todos», ordenar por `m.debutDate`.
-- =====================================================================================
/*
SELECT  m.nameList AS jugador,
        m.mlbID    AS mlb_id,
        CAST(m.debutDate AS date) AS debut,
        YEAR(m.debutDate)         AS temporada,
        (SELECT COUNT(1) FROM dbo.retroDailyReg r WHERE r.PLAYER_ID = m.retroID) AS juegos_carrera
FROM    dbo.dglMaster m
WHERE   m.debutDate IS NOT NULL
ORDER BY MONTH(m.debutDate), DAY(m.debutDate);
*/
