-- =====================================================================================
-- CUATRO O MÁS LANZADORES DOMINICANOS PARA EL MISMO EQUIPO EN UN JUEGO.
--
-- No es la defensa parada en el terreno (eso es `79_seis_dominicanos`): es el desfile del bullpen.
-- Cuatro dominicanos saliendo del mismo bullpen la misma tarde.
--
-- EL UMBRAL, MEDIDO sobre 59.916 juegos-equipo con al menos un lanzador dominicano:
--
--     3 dominicanos    1.071 juegos-equipo    9,23 por temporada   <- rutina
--     4                   89                  0,77                 <- el corte
--     5                    6                  0,05
--     6                    1                  0,01                 <- el récord
--
-- Con 3 son nueve por temporada y deja de ser noticia. Con 4 queda en 0,77 — la misma liga que
-- `hr3` (0,55) y `triples2` (0,65), que es donde vive el inventario. Son 96 en total.
--
-- Los de 5 y 6 NO llevan detector aparte: entran por acá y la magnitud (4.2) los sube sola, que es
-- el patrón de la 5.1.2. El récord se nombra en el texto.
--
-- EL RÉCORD: Pittsburgh Pirates, 3 de junio de 2023 — SEIS lanzadores dominicanos en un juego.
-- Y los Arizona Diamondbacks de 2006 pusieron cinco TRES VECES en dos meses.
--
-- GRANO: el juego-equipo (407.816 = 203.908 juegos × 2 equipos).
--
-- A QUIÉN SE LE ATRIBUYE: al de más juegos de carrera, y el texto los nombra a todos. El porqué está
-- en el preludio `_04_alineaciones.sql`.
-- =====================================================================================
WITH conteo AS (
    SELECT  j.game_id, j.equipo, COUNT(DISTINCT j.PLAYER_ID) AS lanzadores
    FROM    #juegos j
    WHERE   j.P_G >= 1
    GROUP BY j.game_id, j.equipo
    HAVING  COUNT(DISTINCT j.PLAYER_ID) >= 4
),
-- El más reconocible de los que lanzaron, por juegos de carrera. `TOP 1` con `ORDER BY` en vez de
-- un MAX: si dos empatan, el desempate por nombre lo deja estable entre corridas.
elegido AS (
    SELECT  c.game_id, c.equipo, c.lanzadores,
            (SELECT TOP 1 h.mlb_id
             FROM   #juegos j2
             INNER JOIN #huella h ON h.retro_id = j2.PLAYER_ID
             WHERE  j2.game_id = c.game_id AND j2.equipo = c.equipo AND j2.P_G >= 1
             ORDER BY h.juegos DESC, h.nombre) AS mlb_id,
            -- «A, B, C y D» — la coma final se convierte en « y », que es como se lee en voz alta.
            -- LOS DUEÑOS: todos los que lanzaron ese día por ese equipo.
            (SELECT ' ' + STUFF((SELECT ' ' + CAST(h4.mlb_id AS varchar(10))
                                 FROM   #juegos j4
                                 INNER JOIN #huella h4 ON h4.retro_id = j4.PLAYER_ID
                                 WHERE  j4.game_id = c.game_id AND j4.equipo = c.equipo AND j4.P_G >= 1
                                 GROUP BY h4.mlb_id
                                 ORDER BY h4.mlb_id
                                 FOR XML PATH(''), TYPE).value('.', 'nvarchar(max)'), 1, 1, '') + ' '
            ) AS participantes,            (SELECT STUFF(lista, LEN(lista) - CHARINDEX(',', REVERSE(lista)) + 1, 2, ' y ')
             FROM (SELECT STUFF((SELECT ', ' + h2.nombre
                                 FROM   #juegos j3
                                 INNER JOIN #huella h2 ON h2.retro_id = j3.PLAYER_ID
                                 WHERE  j3.game_id = c.game_id AND j3.equipo = c.equipo AND j3.P_G >= 1
                                 GROUP BY h2.nombre
                                 ORDER BY h2.nombre
                                 FOR XML PATH(''), TYPE).value('.', 'nvarchar(max)'), 1, 2, '') AS lista) z
            ) AS quienes
    FROM    conteo c
)
SELECT  'lanzadores_equipo'                       AS tipo,
        '4+ lanzadores dominicanos en un mismo equipo' AS gesta,
        e.participantes,
        'lanzador'                                AS rol,
        'completa'                                AS cobertura,
        407816                                    AS universo,
        -- `situar = 0` por lo mismo que en el jardín y el cuadro (ver docs/EFEMERIDES.md 3.5): la
        -- frase del motor habla de UN dominicano y esto lo hicieron cuatro, cinco o seis a la vez.
        0                                         AS situar,
        CASE e.lanzadores WHEN 4 THEN 'Cuatro' WHEN 5 THEN 'Cinco' ELSE 'Seis' END
            + ' lanzadores dominicanos para {equipo_nombre} en el mismo juego: {detalle}.'
            + CASE WHEN e.lanzadores >= 6 THEN ' Es el máximo que se ha visto.' ELSE '' END AS plantilla,
        e.mlb_id,
        hp.nombre                                 AS nombre,
        f.fecha,
        YEAR(f.fecha)                             AS temporada,
        e.game_id,
        0                                         AS event_id,
        COALESCE(g.game_type, 'R')                AS game_type,
        e.equipo,
        COALESCE(g.rival, '')                     AS rival,
        COALESCE(g.en_casa, 0)                    AS en_casa,
        1                                         AS signo,
        e.lanzadores                              AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        e.quienes                                 AS detalle,
        COALESCE(g.equipo_nombre, '')             AS equipo_nombre,
        COALESCE(g.rival_nombre, '')              AS rival_nombre,
        ''                                        AS oponente
FROM    elegido e
INNER JOIN #huella hp ON hp.mlb_id = e.mlb_id
LEFT  JOIN #fechas f ON f.game_id = e.game_id
-- Una fila cualquiera del equipo en ese juego da el rival, el nombre de época y si era en casa.
OUTER APPLY (SELECT TOP 1 j4.rival, j4.en_casa, j4.equipo_nombre, j4.rival_nombre, j4.game_type
             FROM   #juegos j4
             WHERE  j4.game_id = e.game_id AND j4.equipo = e.equipo) g
WHERE   f.fecha IS NOT NULL AND e.mlb_id IS NOT NULL;

-- =====================================================================================
-- LA LISTA — «¿en qué juegos un equipo usó 4+ lanzadores dominicanos?»
-- =====================================================================================
/*
WITH lanz AS (
    SELECT r.GAME_ID, r.TEAM_ID, r.PLAYER_ID FROM dbo.retroDailyReg r
    INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID WHERE r.P_G >= 1
    UNION
    SELECT p.GAME_ID, p.TEAM_ID, p.PLAYER_ID FROM dbo.retroDailyPost p
    INNER JOIN dbo.dglMaster m ON m.retroID = p.PLAYER_ID WHERE p.P_G >= 1
),
fechas AS (
    SELECT GAME_ID, CAST(GAME_DT AS date) AS fecha FROM dbo.retroGamesReg
    UNION ALL SELECT GAME_ID, CAST(GAME_DT AS date) FROM dbo.retroGamesPost
)
SELECT  f.fecha, l.TEAM_ID AS equipo, COUNT(DISTINCT l.PLAYER_ID) AS lanzadores,
        STUFF((SELECT ', ' + m2.nameList FROM lanz l2
               INNER JOIN dbo.dglMaster m2 ON m2.retroID = l2.PLAYER_ID
               WHERE l2.GAME_ID = l.GAME_ID AND l2.TEAM_ID = l.TEAM_ID
               ORDER BY m2.nameList FOR XML PATH('')), 1, 2, '') AS quienes
FROM    lanz l INNER JOIN fechas f ON f.GAME_ID = l.GAME_ID
GROUP BY l.GAME_ID, l.TEAM_ID, f.fecha
HAVING  COUNT(DISTINCT l.PLAYER_ID) >= 4
ORDER BY lanzadores DESC, f.fecha;
*/
