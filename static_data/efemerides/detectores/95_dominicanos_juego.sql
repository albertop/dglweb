-- =====================================================================================
-- DIEZ O MÁS DOMINICANOS EN UN MISMO JUEGO, contando TODO: los dos equipos, abridores,
-- relevistas, emergentes, corredores emergentes y sustitutos defensivos.
--
-- Es el detector más ancho de la familia y mide otra cosa que sus hermanos: no una formación
-- (`77`, `78`, `79`) ni un bullpen (`93`, `94`), sino CUÁNTO PESA LA REPÚBLICA DOMINICANA EN UN
-- PARTIDO DE GRANDES LIGAS. Cualquiera que puso un pie en el terreno cuenta.
--
-- `retroDaily` tiene una fila por jugador que APARECIÓ en el juego, así que la cuenta sale directa y
-- recoge al emergente que tomó un solo turno igual que al abridor.
--
-- EL UMBRAL, MEDIDO sobre los 107.264 juegos con al menos un dominicano:
--
--      8 dominicanos    660 juegos    5,69 por temporada
--      9                189           1,63
--     10                 42           0,36     <- el corte: 54 juegos de 10 o más, 0,47 al año
--     11                  7           0,06
--     12                  5           0,04     <- el récord
--
-- Con 9 serían 243 juegos (2,09 al año) y con 8, 903. Diez deja 54 en 116 temporadas —0,47 por
-- temporada, la liga de `hr3` (0,55)— y además es una cifra que se dice sola: diez dominicanos en
-- un mismo juego.
--
-- LOS DE 11 Y 12 NO LLEVAN DETECTOR APARTE: entran por acá y la magnitud (4.2) los sube sola, que es
-- el patrón de la 5.1.2. El récord se nombra en el texto.
--
-- POR QUÉ ES MÁS ALTO QUE LOS OTROS. Acá caben 12 y en el terreno a la vez caben 6 (`79`), y no hay
-- contradicción: son preguntas distintas. Seis es cuántos pueden estar parados al mismo tiempo para
-- un equipo; doce es cuántos pasaron por el juego entre los dos.
--
-- GRANO: el juego (203.908).
--
-- A QUIÉN SE LE ATRIBUYE: al de más juegos de carrera. Ver `_04_alineaciones.sql`.
-- =====================================================================================
WITH conteo AS (
    SELECT  j.game_id, COUNT(DISTINCT j.PLAYER_ID) AS dominicanos
    FROM    #juegos j
    GROUP BY j.game_id
    HAVING  COUNT(DISTINCT j.PLAYER_ID) >= 10
),
elegido AS (
    SELECT  c.game_id, c.dominicanos,
            -- LOS DUEÑOS: los diez o doce que pasaron por el juego. La fila es una —el calendario
            -- no puede decir doce veces lo mismo el mismo día— pero el perfil de cada uno la
            -- encuentra por acá. Ver `exportar_efemerides.ps1`.
            (SELECT ' ' + STUFF((SELECT ' ' + CAST(h4.mlb_id AS varchar(10))
                                 FROM   #juegos j4
                                 INNER JOIN #huella h4 ON h4.retro_id = j4.PLAYER_ID
                                 WHERE  j4.game_id = c.game_id
                                 GROUP BY h4.mlb_id
                                 ORDER BY h4.mlb_id
                                 FOR XML PATH(''), TYPE).value('.', 'nvarchar(max)'), 1, 1, '') + ' '
            ) AS participantes,
            (SELECT TOP 1 h.mlb_id
             FROM   #juegos j2
             INNER JOIN #huella h ON h.retro_id = j2.PLAYER_ID
             WHERE  j2.game_id = c.game_id
             ORDER BY h.juegos DESC, h.nombre) AS mlb_id
    FROM    conteo c
)
SELECT  'dominicanos_juego'                       AS tipo,
        '10+ dominicanos en un mismo juego' AS gesta,
        e.participantes,
        'fildeador'                               AS rol,
        'completa'                                AS cobertura,
        203908                                    AS universo,
        -- `situar = 0`: son diez o doce hombres, y de los dos equipos. Ver docs/EFEMERIDES.md 3.5.
        0                                         AS situar,
        CASE e.dominicanos WHEN 10 THEN 'Diez' WHEN 11 THEN 'Once' ELSE 'Doce' END
            + ' dominicanos en el mismo juego, {equipo_nombre} contra {rival_nombre}, entre los dos equipos.'
            + CASE WHEN e.dominicanos >= 12 THEN ' Es el máximo que se ha visto.' ELSE '' END AS plantilla,
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
        e.dominicanos                             AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        ''                                        AS detalle,
        COALESCE(g.equipo_nombre, '')             AS equipo_nombre,
        COALESCE(g.rival_nombre, '')              AS rival_nombre,
        ''                                        AS oponente
FROM    elegido e
INNER JOIN #huella hp ON hp.mlb_id = e.mlb_id
LEFT  JOIN #fechas f ON f.game_id = e.game_id
-- El juego se nombra «local contra visitante»: la gesta es del partido, no de un bando.
OUTER APPLY (SELECT TOP 1 j4.equipo, j4.rival, j4.equipo_nombre, j4.rival_nombre, j4.game_type
             FROM   #juegos j4
             WHERE  j4.game_id = e.game_id AND j4.en_casa = 1) g
WHERE   f.fecha IS NOT NULL AND e.mlb_id IS NOT NULL;

-- =====================================================================================
-- LA LISTA — «¿en qué juegos hubo diez o más dominicanos?»
-- =====================================================================================
/*
WITH p AS (
    SELECT r.GAME_ID, r.PLAYER_ID FROM dbo.retroDailyReg r
    INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
    UNION
    SELECT o.GAME_ID, o.PLAYER_ID FROM dbo.retroDailyPost o
    INNER JOIN dbo.dglMaster m2 ON m2.retroID = o.PLAYER_ID
),
fechas AS (
    SELECT GAME_ID, CAST(GAME_DT AS date) AS fecha FROM dbo.retroGamesReg
    UNION ALL SELECT GAME_ID, CAST(GAME_DT AS date) FROM dbo.retroGamesPost
)
SELECT  f.fecha, COUNT(DISTINCT p.PLAYER_ID) AS dominicanos,
        STUFF((SELECT ', ' + m3.nameList FROM p p2
               INNER JOIN dbo.dglMaster m3 ON m3.retroID = p2.PLAYER_ID
               WHERE p2.GAME_ID = p.GAME_ID
               ORDER BY m3.nameList FOR XML PATH('')), 1, 2, '') AS quienes
FROM    p INNER JOIN fechas f ON f.GAME_ID = p.GAME_ID
GROUP BY p.GAME_ID, f.fecha
HAVING  COUNT(DISTINCT p.PLAYER_ID) >= 10
ORDER BY dominicanos DESC, f.fecha;
*/
