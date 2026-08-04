-- =====================================================================================
-- CINCO O MÁS LANZADORES DOMINICANOS EN UN MISMO JUEGO, CONTANDO LOS DOS EQUIPOS.
--
-- El hermano de `93_lanzadores_equipo`, un escalón más arriba: no importa de qué lado salieron.
-- Es la foto de cuánto pesa la República Dominicana en un partido de Grandes Ligas.
--
-- EL UMBRAL, MEDIDO sobre 49.866 juegos con al menos un lanzador dominicano:
--
--     4 dominicanos     657 juegos    5,66 por temporada   <- rutina
--     5                 117           1,01                 <- el corte
--     6                  17           0,15
--     7                   2           0,02                 <- el récord
--
-- Cinco da exactamente UNO POR TEMPORADA, que es el criterio con que se cortaron `hr480`, los fouls
-- y los pelotazos. Con cuatro serían casi seis por año. Son 136 en total.
--
-- POR QUÉ EL UMBRAL ES 5 Y NO 4, SI EN `93` ES 4. Porque el universo es otro: acá caben los dos
-- bullpens, así que juntar cuatro dominicanos es bastante más fácil que juntarlos en uno solo. Los
-- dos umbrales salen del MISMO criterio —cortar donde deja de ser rutina— aplicado a dos
-- distribuciones distintas. Que den números distintos es la señal de que el criterio se aplicó.
--
-- EL RÉCORD SON SIETE, y ha pasado dos veces:
--
--     2006-09-16   Vargas, Mesa, Valverde, Cruz, Vizcaíno, Ramírez y Peña
--     2023-07-30   Perdomo, Sánchez, Moreta, Soto, Hernández, Domínguez y Marte
--
-- SE SOLAPA CON EL 93 A PROPÓSITO. Un juego donde un equipo puso cinco casi siempre tiene cinco o
-- más en total, así que los dos detectores disparan. La fusión (sección 7) se queda con el de MAYOR
-- RAREZA —el del mismo equipo, que es la gesta más específica— y el otro queda de etiqueta. Eso es
-- exactamente lo que la regla de fusión existe para resolver.
--
-- GRANO: el juego (203.908).
--
-- A QUIÉN SE LE ATRIBUYE: al de más juegos de carrera. Ver `_04_alineaciones.sql`.
-- =====================================================================================
WITH conteo AS (
    SELECT  j.game_id, COUNT(DISTINCT j.PLAYER_ID) AS lanzadores
    FROM    #juegos j
    WHERE   j.P_G >= 1
    GROUP BY j.game_id
    HAVING  COUNT(DISTINCT j.PLAYER_ID) >= 5
),
elegido AS (
    SELECT  c.game_id, c.lanzadores,
            (SELECT TOP 1 h.mlb_id
             FROM   #juegos j2
             INNER JOIN #huella h ON h.retro_id = j2.PLAYER_ID
             WHERE  j2.game_id = c.game_id AND j2.P_G >= 1
             ORDER BY h.juegos DESC, h.nombre) AS mlb_id,
            (SELECT STUFF(lista, LEN(lista) - CHARINDEX(',', REVERSE(lista)) + 1, 2, ' y ')
             FROM (SELECT STUFF((SELECT ', ' + h2.nombre
                                 FROM   #juegos j3
                                 INNER JOIN #huella h2 ON h2.retro_id = j3.PLAYER_ID
                                 WHERE  j3.game_id = c.game_id AND j3.P_G >= 1
                                 GROUP BY h2.nombre
                                 ORDER BY h2.nombre
                                 FOR XML PATH(''), TYPE).value('.', 'nvarchar(max)'), 1, 2, '') AS lista) z
            ) AS quienes
    FROM    conteo c
)
SELECT  'lanzadores_juego'                        AS tipo,
        'lanzador'                                AS rol,
        'completa'                                AS cobertura,
        203908                                    AS universo,
        -- `situar = 0`: son cinco, seis o siete hombres, y de los dos equipos. Ver 3.5.
        0                                         AS situar,
        CASE e.lanzadores WHEN 5 THEN 'Cinco' WHEN 6 THEN 'Seis' ELSE 'Siete' END
            + ' lanzadores dominicanos en el mismo juego, {equipo_nombre} contra {rival_nombre}: {detalle}.'
            + CASE WHEN e.lanzadores >= 7 THEN ' Es el máximo que se ha visto.' ELSE '' END AS plantilla,
        e.mlb_id,
        hp.nombre                                 AS nombre,
        f.fecha,
        YEAR(f.fecha)                             AS temporada,
        e.game_id,
        0                                         AS event_id,
        COALESCE(g.game_type, 'R')                AS game_type,
        COALESCE(g.equipo, '')                    AS equipo,
        COALESCE(g.rival, '')                     AS rival,
        1                                         AS en_casa,
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
-- EL JUEGO SE NOMBRA «LOCAL CONTRA VISITANTE», no desde el equipo del jugador elegido. La gesta es
-- del partido entero, así que el punto de vista tiene que ser el del partido y no el de un bando.
OUTER APPLY (SELECT TOP 1 j4.equipo, j4.rival, j4.equipo_nombre, j4.rival_nombre, j4.game_type
             FROM   #juegos j4
             WHERE  j4.game_id = e.game_id AND j4.en_casa = 1) g
WHERE   f.fecha IS NOT NULL AND e.mlb_id IS NOT NULL;

-- =====================================================================================
-- LA LISTA — «¿en qué juegos hubo 5+ lanzadores dominicanos entre los dos equipos?»
-- =====================================================================================
/*
WITH lanz AS (
    SELECT r.GAME_ID, r.PLAYER_ID FROM dbo.retroDailyReg r
    INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID WHERE r.P_G >= 1
    UNION
    SELECT p.GAME_ID, p.PLAYER_ID FROM dbo.retroDailyPost p
    INNER JOIN dbo.dglMaster m ON m.retroID = p.PLAYER_ID WHERE p.P_G >= 1
),
fechas AS (
    SELECT GAME_ID, CAST(GAME_DT AS date) AS fecha FROM dbo.retroGamesReg
    UNION ALL SELECT GAME_ID, CAST(GAME_DT AS date) FROM dbo.retroGamesPost
)
SELECT  f.fecha, COUNT(DISTINCT l.PLAYER_ID) AS lanzadores,
        STUFF((SELECT ', ' + m2.nameList FROM lanz l2
               INNER JOIN dbo.dglMaster m2 ON m2.retroID = l2.PLAYER_ID
               WHERE l2.GAME_ID = l.GAME_ID
               ORDER BY m2.nameList FOR XML PATH('')), 1, 2, '') AS quienes
FROM    lanz l INNER JOIN fechas f ON f.GAME_ID = l.GAME_ID
GROUP BY l.GAME_ID, f.fecha
HAVING  COUNT(DISTINCT l.PLAYER_ID) >= 5
ORDER BY lanzadores DESC, f.fecha;
*/
