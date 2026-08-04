-- =====================================================================================
-- DEBUTÓ A LOS 30 AÑOS O MÁS. Medido: 9 dominicanos.
--
-- El contrario exacto de `11_debut_joven.sql`, y la historia que cuenta es otra: no es precocidad,
-- es persistencia. Llegar a Grandes Ligas pasados los treinta significa haber estado años en el
-- camino sin que nadie lo llamara.
--
-- EL UMBRAL, sobre los 961 debuts con edad fiable (edad media: 23,5 años):
--
--     29 o más   19 debuts   2,0 %
--     30 o más    9          0,9 %   <- el corte
--     31 o más    5          0,5 %   <- se queda corto
--
-- Treinta es además la frontera de la que habla la gente, igual que los 20 del otro lado.
--
-- LOS DOS MÁS VIEJOS SON HERMANOS, y eso solo lo encuentra un detector como este:
--
--     41 años   Guayubín Olivo   1960-09-05
--     35 años   Chichí Olivo     1961-06-05
--
-- Los hermanos Olivo, de Guayubín, debutaron con 41 y 35 años y son los dos debutantes dominicanos
-- más viejos de la historia. Detrás vienen Ángel Castro y Huáscar Brazobán con 32, Federico Velázquez
-- con 31, y con 30 Rufino Linares, Jumbo Díaz, Edward Paredes y Webster Rivas.
--
-- RUFINO LINARES APARECE TAMBIÉN EN `97_debut_dificil.sql` —el peor debut dominicano por valor de
-- carreras— y las dos efemérides son del mismo día. No se fusionan: `debut_dificil` cuelga del juego
-- y esta no, así que llevan `game_id` distinto. Es correcto que salgan las dos: son dos cosas
-- distintas del mismo hombre.
--
-- SE FUSIONA CON `91_debut.sql`, igual que su hermano de los 20 años, y por la misma razón.
--
-- GRANO: el debut. `N` = 961, los debuts con edad fiable.
-- =====================================================================================
SELECT  'debut_veterano' AS tipo,
        'un debut a los 30 años o más' AS gesta,
        'persona' AS rol,
        'completa' AS cobertura,
        961 AS universo,
        1 AS situar,
        'Debutó en Grandes Ligas a los {detalle} años, cuando casi nadie debuta ya.' AS plantilla,
        m.mlbID AS mlb_id,
        m.nameList AS nombre,
        DATEFROMPARTS(YEAR(GETDATE()), MONTH(m.debutDate), DAY(m.debutDate)) AS fecha,
        YEAR(m.debutDate) AS temporada,
        '' AS game_id, 0 AS event_id, '-' AS game_type,
        '' AS equipo, '' AS rival, 0 AS en_casa,
        1 AS signo,
        -- Acá la edad va derecha: más viejo, más gesta. No hay que invertir nada.
        DATEDIFF(YEAR, m.birthDate, m.debutDate)
          - CASE WHEN MONTH(m.debutDate) < MONTH(m.birthDate)
                   OR (MONTH(m.debutDate) = MONTH(m.birthDate) AND DAY(m.debutDate) < DAY(m.birthDate))
                 THEN 1 ELSE 0 END AS magnitud,
        NULL AS wpa_jugador, NULL AS li_max,
        CAST(DATEDIFF(YEAR, m.birthDate, m.debutDate)
             - CASE WHEN MONTH(m.debutDate) < MONTH(m.birthDate)
                      OR (MONTH(m.debutDate) = MONTH(m.birthDate) AND DAY(m.debutDate) < DAY(m.birthDate))
                    THEN 1 ELSE 0 END AS varchar(3)) AS detalle,
        '' AS equipo_nombre, '' AS rival_nombre, '' AS oponente
FROM    dbo.dglMaster m
WHERE   m.debutDate IS NOT NULL
  AND   m.birthDate IS NOT NULL
  AND   NOT (MONTH(m.debutDate) = 1 AND DAY(m.debutDate) = 1)
  AND   m.retroID NOT IN (SELECT retro_id FROM #sin_natalicio)
  AND   (DATEDIFF(YEAR, m.birthDate, m.debutDate)
         - CASE WHEN MONTH(m.debutDate) < MONTH(m.birthDate)
                  OR (MONTH(m.debutDate) = MONTH(m.birthDate) AND DAY(m.debutDate) < DAY(m.birthDate))
                THEN 1 ELSE 0 END) >= 30;

-- =====================================================================================
-- LA LISTA — «¿quiénes debutaron pasados los 30?»
-- =====================================================================================
/*
SELECT  m.nameList AS jugador, CAST(m.debutDate AS date) AS debut,
        DATEDIFF(YEAR, m.birthDate, m.debutDate)
          - CASE WHEN MONTH(m.debutDate) < MONTH(m.birthDate)
                   OR (MONTH(m.debutDate) = MONTH(m.birthDate) AND DAY(m.debutDate) < DAY(m.birthDate))
                 THEN 1 ELSE 0 END AS edad,
        (SELECT COUNT(1) FROM dbo.retroDailyReg r WHERE r.PLAYER_ID = m.retroID) AS juegos_carrera
FROM    dbo.dglMaster m
WHERE   m.debutDate IS NOT NULL AND m.birthDate IS NOT NULL
  AND   NOT (MONTH(m.debutDate) = 1 AND DAY(m.debutDate) = 1)
ORDER BY edad DESC, debut;
*/
