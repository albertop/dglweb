-- =====================================================================================
-- LOS TRES JARDINEROS, DOMINICANOS.
--
-- Los tres puestos del jardín ocupados por dominicanos a la vez, en la misma media entrada.
--
-- Medido: 131 juegos. El primero es de 1962 y el más famoso de 1963:
--
--     1962-04-16   Manuel Mota / Mateo Alou / Felipe Alou
--     1963-09-15   Mateo Alou / Felipe Alou / Jesús Alou   <- los TRES HERMANOS
--
-- GRANO: el juego-equipo (407.816 = 203.908 juegos × 2 equipos). La condición se comprueba por media
-- entrada —es cuando los tres están de verdad en el terreno al mismo tiempo— pero la efeméride es
-- del juego: «un día como hoy» no distingue entradas.
--
-- A QUIÉN SE LE ATRIBUYE: al de más juegos de carrera, y el texto nombra a los tres. El porqué está
-- en el preludio `_04_alineaciones.sql`.
-- =====================================================================================
WITH juegos_con_jardin AS (
    SELECT  d.game_id,
            MIN(d.batea_casa) AS batea_casa,
            MIN(d.p7) AS p7, MIN(d.p8) AS p8, MIN(d.p9) AS p9
    FROM    #defensa d
    INNER JOIN #huella h7 ON h7.retro_id = d.p7
    INNER JOIN #huella h8 ON h8.retro_id = d.p8
    INNER JOIN #huella h9 ON h9.retro_id = d.p9
    GROUP BY d.game_id
),
-- El más reconocible de los tres, por juegos de carrera. `TOP 1` con `ORDER BY` en vez de un MAX
-- con subconsulta: si dos empatan, el desempate por nombre lo deja estable entre corridas.
elegido AS (
    SELECT  j.game_id, j.batea_casa, j.p7, j.p8, j.p9,
            (SELECT TOP 1 h.mlb_id FROM #huella h
             WHERE h.retro_id IN (j.p7, j.p8, j.p9)
             ORDER BY h.juegos DESC, h.nombre) AS mlb_id
    FROM    juegos_con_jardin j
)
SELECT  'jardin_dominicano'                       AS tipo,
        'el jardín entero dominicano' AS gesta,
        'fildeador'                               AS rol,
        'completa'                                AS cobertura,
        0                                         AS situar,
        407816                                    AS universo,
        -- `situar = 0`: la frase del motor habla de UN dominicano y esto lo hicieron tres o cuatro a la
        -- vez. Decía «Fue el primer dominicano en lograrlo», que es un disparate para una gesta
        -- colectiva. Lo que sí vale —que fue la primera vez que se vio— se calcula acá.
        'Los tres jardineros de {equipo_nombre} fueron dominicanos: {detalle}.'
            + CASE WHEN e.game_id = (SELECT TOP 1 x.game_id FROM elegido x
                                     INNER JOIN #fechas xf ON xf.game_id = x.game_id
                                     ORDER BY xf.fecha, x.game_id)
                   THEN ' Fue la primera vez que se vio.' ELSE '' END AS plantilla,
        e.mlb_id,
        hp.nombre                                 AS nombre,
        f.fecha,
        YEAR(f.fecha)                             AS temporada,
        e.game_id,
        0                                         AS event_id,
        'R'                                       AS game_type,
        -- LA DEFENSA ES EL EQUIPO QUE NO BATEA. `batea_casa = 1` significa que los jardineros son
        -- los visitantes: es la vuelta contraria a la de los detectores de bateo.
        CASE WHEN e.batea_casa = 1 THEN g.AWAY_TEAM_ID ELSE g.HOME_TEAM_ID END AS equipo,
        CASE WHEN e.batea_casa = 1 THEN g.HOME_TEAM_ID ELSE g.AWAY_TEAM_ID END AS rival,
        CASE WHEN e.batea_casa = 1 THEN 0 ELSE 1 END AS en_casa,
        1                                         AS signo,
        3                                         AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        h7.nombre + ', ' + h8.nombre + ' y ' + h9.nombre AS detalle,
        COALESCE(eq.nombre, '')                   AS equipo_nombre,
        COALESCE(ri.nombre, '')                   AS rival_nombre,
        ''                                        AS oponente
FROM    elegido e
INNER JOIN #huella h7 ON h7.retro_id = e.p7
INNER JOIN #huella h8 ON h8.retro_id = e.p8
INNER JOIN #huella h9 ON h9.retro_id = e.p9
INNER JOIN #huella hp ON hp.mlb_id  = e.mlb_id
LEFT  JOIN #fechas f ON f.game_id = e.game_id
LEFT  JOIN dbo.retroGamesReg g ON g.GAME_ID = e.game_id
LEFT  JOIN #equipos eq ON eq.codigo = CASE WHEN e.batea_casa = 1 THEN g.AWAY_TEAM_ID ELSE g.HOME_TEAM_ID END
                      AND f.fecha BETWEEN eq.desde AND eq.hasta
LEFT  JOIN #equipos ri ON ri.codigo = CASE WHEN e.batea_casa = 1 THEN g.HOME_TEAM_ID ELSE g.AWAY_TEAM_ID END
                      AND f.fecha BETWEEN ri.desde AND ri.hasta
WHERE   f.fecha IS NOT NULL;

-- =====================================================================================
-- LA LISTA — «¿en qué juegos fueron los tres jardineros dominicanos?»
-- =====================================================================================
/*
WITH med AS (
    SELECT e.GAME_ID, MIN(e.POS7_FLD_ID) AS p7, MIN(e.POS8_FLD_ID) AS p8, MIN(e.POS9_FLD_ID) AS p9
    FROM   dbo.retroEventsReg e GROUP BY e.GAME_ID, e.INN_CT, e.BAT_HOME_ID
)
SELECT  DISTINCT CAST(g.GAME_DT AS date) AS fecha,
        n7.nameList AS jardin_izquierdo, n8.nameList AS jardin_central, n9.nameList AS jardin_derecho
FROM    med m
INNER JOIN dbo.dglMaster n7 ON n7.retroID = m.p7
INNER JOIN dbo.dglMaster n8 ON n8.retroID = m.p8
INNER JOIN dbo.dglMaster n9 ON n9.retroID = m.p9
LEFT  JOIN dbo.retroGamesReg g ON g.GAME_ID = m.GAME_ID
ORDER BY fecha;
*/
