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
        -- «A LOS X AÑOS» Y NO «HACE X AÑOS» (dueño, 2026-08-04). Es la misma corrección que ya se
        -- hizo en `92_fallecimiento.sql`: la edad dice algo del hombre —debutar a los 19 no es lo
        -- mismo que debutar a los 28— mientras que los años transcurridos solo dicen en qué año
        -- estamos, y encima envejecen solos cada 1 de enero.
        --
        -- Sin natalicio confiable no se dice la edad, por lo mismo que allá: seria una cifra falsa
        -- con toda la seguridad de una cifra exacta. Ver `_00_comun.sql`.
        CASE WHEN m.retroID IN (SELECT retro_id FROM #sin_natalicio) OR m.birthDate IS NULL
             THEN 'Debutó en Grandes Ligas en {temporada}.'
             ELSE 'Debutó en Grandes Ligas a los {detalle} años.' END AS plantilla,
        m.mlbID AS mlb_id,
        m.nameList AS nombre,
        DATEFROMPARTS(YEAR(GETDATE()), MONTH(m.debutDate), DAY(m.debutDate)) AS fecha,
        YEAR(m.debutDate) AS temporada,
        '' AS game_id, 0 AS event_id, '-' AS game_type,
        '' AS equipo, '' AS rival, 0 AS en_casa,
        1 AS signo,
        COALESCE((SELECT COUNT(1) FROM dbo.retroDailyReg r WHERE r.PLAYER_ID = m.retroID), 0) AS magnitud,
        NULL AS wpa_jugador, NULL AS li_max,
        -- LA EDAD AL DEBUTAR, con el mismo descuento que la edad al morir: `DATEDIFF(YEAR, ...)`
        -- cuenta fronteras de año calendario, no cumpleaños, así que hay que restar uno cuando el
        -- cumpleaños todavía no había llegado ese año. Sin eso, un nacido en noviembre que debuta en
        -- abril sale con un año de más.
        CAST(
            DATEDIFF(YEAR, m.birthDate, m.debutDate)
            - CASE WHEN MONTH(m.debutDate) < MONTH(m.birthDate)
                     OR (MONTH(m.debutDate) = MONTH(m.birthDate) AND DAY(m.debutDate) < DAY(m.birthDate))
                   THEN 1 ELSE 0 END
        AS varchar(3)) AS detalle,
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
