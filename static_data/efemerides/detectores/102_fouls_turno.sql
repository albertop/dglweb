-- =====================================================================================
-- DIEZ O MÁS FOULS EN UN SOLO TURNO. Medido: 10 turnos, 10 bateadores.
--
-- El turno que no se acaba: el bateador va tirando la pelota de foul una y otra vez hasta que pasa
-- algo. Es de las cosas que el público recuerda de un juego entero.
--
-- Estaba diseñado desde el principio y nunca se había construir — figuraba en la 5.12. Lo reclamó el
-- dueño el 2026-08-04.
--
-- EL UMBRAL, sobre los 392.630 turnos dominicanos con Statcast (2008-2026):
--
--      8 fouls   92 turnos, 49 bateadores   4,8 por temporada   <- rutina
--      9         30, 25                     1,6
--     10         10, 10                     0,5                 <- el corte
--     11          5,  5                     0,3
--     12          1,  1                     0,1                 <- el récord
--
-- Diez son diez turnos en diecinueve temporadas, y CADA BATEADOR APARECE UNA SOLA VEZ: no hay
-- reincidentes, lo que dice bastante de lo raro que es.
--
-- SE CUENTAN CUATRO CLASES DE FOUL: `foul`, `foul_tip`, `foul_bunt` y `bunt_foul_tip`. El
-- `foul_pitchout` se deja fuera —hay cuatro en toda la base— porque no es un swing del bateador.
--
-- EL TURNO SE IDENTIFICA CON `at_bat_number`, que Statcast trae y numera dentro del juego. Sin esa
-- columna habría que reconstruirlo por conteo de bolas y strikes, que es frágil.
--
-- ⚠️ COBERTURA PARCIAL, 2008 en adelante. NO publica totales — antes de Statcast nadie contaba los
-- fouls lanzamiento por lanzamiento. Ver docs/EFEMERIDES.md 5.3.
--
-- GRANO: el turno con Statcast (392.630).
-- =====================================================================================
SELECT  'fouls_turno' AS tipo,
        '10+ fouls en un solo turno' AS gesta,
        'bateador'                                AS rol,
        'parcial'                                 AS cobertura,
        392630                                    AS universo,
        1                                         AS situar,
        'Peleó un turno de {detalle} contra {rival_nombre}.' AS plantilla,
        p.mlb_id, p.nombre, p.fecha, p.temporada, p.game_id,
        0                                         AS event_id,
        p.game_type, p.equipo, p.rival, p.en_casa,
        1                                         AS signo,
        s.fouls                                   AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        CAST(s.fouls AS varchar(3)) + ' fouls seguidos'
            + CASE WHEN s.lanzamientos > 0
                   THEN ', ' + CAST(s.lanzamientos AS varchar(3)) + ' lanzamientos en total'
                   ELSE '' END                    AS detalle,
        p.equipo_nombre, p.rival_nombre,
        ''                                        AS oponente
FROM    #puente p
INNER JOIN (
    -- Un turno = (bateador, fecha, at_bat_number). Se queda el de más fouls de cada juego: si un
    -- bateador tuvo dos turnos largos el mismo día, la efeméride es del más largo — no dos filas
    -- del mismo hombre y el mismo día, que la fusión colapsaría igual.
    SELECT  t.batter, t.fecha, MAX(t.fouls) AS fouls, MAX(t.lanzamientos) AS lanzamientos
    FROM (
        SELECT  s.batter, CAST(s.game_date AS date) AS fecha, s.at_bat_number,
                SUM(CASE WHEN s.description IN ('foul','foul_tip','foul_bunt','bunt_foul_tip')
                         THEN 1 ELSE 0 END) AS fouls,
                COUNT(1) AS lanzamientos
        FROM    dbo.scastPitch s
        WHERE   s.game_type = 'R'      -- solo temporada regular, ver `_00_comun.sql`
        GROUP BY s.batter, CAST(s.game_date AS date), s.at_bat_number
    ) t
    WHERE   t.fouls >= 10
    GROUP BY t.batter, t.fecha
) s ON s.batter = p.mlb_id AND s.fecha = p.fecha;

-- =====================================================================================
-- LA LISTA — «¿cuáles son los turnos más largos de un dominicano?»
-- =====================================================================================
/*
SELECT  m.nameList AS bateador, CAST(s.game_date AS date) AS fecha, s.at_bat_number AS turno,
        SUM(CASE WHEN s.description IN ('foul','foul_tip','foul_bunt','bunt_foul_tip') THEN 1 ELSE 0 END) AS fouls,
        COUNT(1) AS lanzamientos
FROM    dbo.scastPitch s
INNER JOIN dbo.dglMaster m ON m.mlbID = s.batter
WHERE   s.game_type = 'R'
GROUP BY m.nameList, CAST(s.game_date AS date), s.at_bat_number
HAVING  SUM(CASE WHEN s.description IN ('foul','foul_tip','foul_bunt','bunt_foul_tip') THEN 1 ELSE 0 END) >= 10
ORDER BY fouls DESC;
*/
