-- =====================================================================================
-- DEBUTÓ ANTES DE CUMPLIR 20 AÑOS. Medido: 15 dominicanos.
--
-- EL UMBRAL, sobre los 961 debuts con edad fiable (edad media: 23,5 años):
--
--     menos de 19    3 debuts   0,3 %   <- demasiado poco, quedaría en anécdota
--     menos de 20   15          1,6 %   <- el corte
--     menos de 21   55          5,7 %   <- ya es zona corriente
--
-- Veinte es además la frontera que la gente usa: «llegó siendo un adolescente». Los quince, con los
-- tres de 18 a la cabeza:
--
--     18   Alfredo Griffin (1976)   José Rijo (1984)   Alex Rodríguez (1994)
--     19   César Cedeño (1970)   Miguel Diloné (1974)   Nelson Norman (1978)
--          Gilberto Reyes (1983)   Junior Noboa (1984)   Manny Lee (1985)
--          Aramis Ramírez (1998)   Adrián Beltré (1998)   Wilson Betemit (2001)   …
--
-- Y la lista se defiende sola: Griffin, Rodríguez, Cedeño, Ramírez y Beltré juntan más de 11.000
-- juegos de Grandes Ligas entre los cinco.
--
-- LA EDAD VA EN AÑOS Y DÍAS (dueño, 2026-08-04), y en este detector es lo que da la noticia. «18
-- años» tapa la diferencia entre el que debutó recién cumplidos y el que estaba a una semana de
-- cumplir 19, y en precocidad esa diferencia ES el dato — así se cuentan estos récords en el béisbol.
--
-- SE FUSIONA CON `91_debut.sql` A PROPÓSITO. Los dos son del mismo hombre, el mismo día y sin juego
-- —`game_id` vacío, `event_id` cero— así que caen en la misma clave de fusión (sección 7). Manda
-- este, que tiene mucha más rareza, y el debut simple queda de etiqueta. Es lo correcto: «debutó a
-- los 18 años» dice todo lo que decía el otro y además dice por qué es noticia.
--
-- QUIÉNES QUEDAN FUERA, y es la misma regla que en `91_debut.sql`: los cuatro debuts del 1 de enero
-- —relleno de Ligas Negras— y quien no tenga natalicio confiable, porque sin fecha de nacimiento no
-- hay edad que calcular. Ver `_00_comun.sql`.
--
-- GRANO: el debut. `N` = 961, los debuts con edad fiable. No son los 292.948 juegos-jugador: la
-- oportunidad de debutar joven se tiene UNA vez en la vida.
-- =====================================================================================
WITH base AS (
    SELECT  m.mlbID, m.nameList, m.debutDate, m.birthDate,
            -- Los años cumplidos, con el descuento de cumpleaños no llegado: `DATEDIFF(YEAR, ...)`
            -- cuenta fronteras de año calendario, no cumpleaños.
            DATEDIFF(YEAR, m.birthDate, m.debutDate)
              - CASE WHEN MONTH(m.debutDate) < MONTH(m.birthDate)
                       OR (MONTH(m.debutDate) = MONTH(m.birthDate) AND DAY(m.debutDate) < DAY(m.birthDate))
                     THEN 1 ELSE 0 END AS anios
    FROM    dbo.dglMaster m
    WHERE   m.debutDate IS NOT NULL
      AND   m.birthDate IS NOT NULL
      AND   NOT (MONTH(m.debutDate) = 1 AND DAY(m.debutDate) = 1)
      AND   m.retroID NOT IN (SELECT retro_id FROM #sin_natalicio)
),
edad AS (
    -- Los DÍAS desde el último cumpleaños antes del debut: se le suman los años al natalicio y se
    -- resta. Sale exacto sin tener que pensar en bisiestos.
    SELECT  b.*, DATEDIFF(DAY, DATEADD(YEAR, b.anios, b.birthDate), b.debutDate) AS dias
    FROM    base b
)
SELECT  'debut_joven' AS tipo,
        'un debut antes de los 20 años' AS gesta,
        '' AS participantes,
        'persona' AS rol,
        'completa' AS cobertura,
        961 AS universo,
        1 AS situar,
        'Debutó en Grandes Ligas con {detalle}.' AS plantilla,
        e.mlbID AS mlb_id,
        e.nameList AS nombre,
        DATEFROMPARTS(YEAR(GETDATE()), MONTH(e.debutDate), DAY(e.debutDate)) AS fecha,
        YEAR(e.debutDate) AS temporada,
        '' AS game_id, 0 AS event_id, '-' AS game_type,
        '' AS equipo, '' AS rival, 0 AS en_casa,
        1 AS signo,
        -- MÁS JOVEN, MÁS GESTA: se invierte para que el percentil ordene al revés. Y se cuenta en
        -- DÍAS, no en años, para que dos debutantes de la misma edad en años no queden empatados.
        (20 * 365) - (e.anios * 365 + e.dias) AS magnitud,
        NULL AS wpa_jugador, NULL AS li_max,
        -- AÑOS Y DÍAS. La concordancia se resuelve acá: «1 día» y no «1 días».
        CAST(e.anios AS varchar(3)) + ' años y ' + CAST(e.dias AS varchar(3))
            + CASE WHEN e.dias = 1 THEN ' día' ELSE ' días' END AS detalle,
        '' AS equipo_nombre, '' AS rival_nombre, '' AS oponente
FROM    edad e
WHERE   e.anios < 20;

-- =====================================================================================
-- LA LISTA — «¿quiénes debutaron antes de los 20?»
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
ORDER BY edad, debut;
*/
