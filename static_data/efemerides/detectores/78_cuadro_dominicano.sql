-- =====================================================================================
-- LOS CUATRO DEL CUADRO, DOMINICANOS.
--
-- Primera, segunda, tercera y el campocorto ocupados por dominicanos a la vez, en la misma media entrada.
--
-- Medido: 12 juegos. Es CUATRO veces más raro que el jardín (131), y en 116 temporadas NUNCA se ha
-- dado el jardín y el cuadro dominicanos en el mismo juego.
-- GRANO: el juego-equipo (407.816 = 203.908 juegos × 2 equipos). La condición se comprueba por media
-- entrada —es cuando los tres están de verdad en el terreno al mismo tiempo— pero la efeméride es
-- del juego: «un día como hoy» no distingue entradas.
--
-- A QUIÉN SE LE ATRIBUYE: al de más juegos de carrera, y el texto nombra a los tres. El porqué está
-- en el preludio `_04_alineaciones.sql`.
-- =====================================================================================
WITH juegos_con_cuadro AS (
    SELECT  d.game_id,
            MIN(d.batea_casa) AS batea_casa,
            MIN(d.p3) AS p3, MIN(d.p4) AS p4, MIN(d.p5) AS p5, MIN(d.p6) AS p6
    FROM    #defensa d
    INNER JOIN #huella h3 ON h3.retro_id = d.p3
    INNER JOIN #huella h4 ON h4.retro_id = d.p4
    INNER JOIN #huella h5 ON h5.retro_id = d.p5
    INNER JOIN #huella h6 ON h6.retro_id = d.p6
    GROUP BY d.game_id
),
-- El más reconocible de los tres, por juegos de carrera. `TOP 1` con `ORDER BY` en vez de un MAX
-- con subconsulta: si dos empatan, el desempate por nombre lo deja estable entre corridas.
elegido AS (
    SELECT  j.game_id, j.batea_casa, j.p3, j.p4, j.p5, j.p6,
            (SELECT TOP 1 h.mlb_id FROM #huella h
             WHERE h.retro_id IN (j.p3, j.p4, j.p5, j.p6)
             ORDER BY h.juegos DESC, h.nombre) AS mlb_id
    FROM    juegos_con_cuadro j
)
SELECT  'cuadro_dominicano'                       AS tipo,
        'el cuadro entero dominicano' AS gesta,
        -- LOS CUATRO DUEÑOS. La fila se atribuye al más reconocible, pero el cuadro fue de los cuatro
        -- y el perfil de cada uno tiene que encontrarla. Ver `exportar_efemerides.ps1`.
        ' ' + CAST(h3.mlb_id AS varchar(10)) + ' ' + CAST(h4.mlb_id AS varchar(10)) + ' '
            + CAST(h5.mlb_id AS varchar(10)) + ' ' + CAST(h6.mlb_id AS varchar(10)) + ' ' AS participantes,
        'fildeador'                               AS rol,
        'completa'                                AS cobertura,
        0                                         AS situar,
        407816                                    AS universo,
        -- `situar = 0`: la frase del motor habla de UN dominicano y esto lo hicieron tres o cuatro a la
        -- vez. Decía «Fue el primer dominicano en lograrlo», que es un disparate para una gesta
        -- colectiva. Lo que sí vale —que fue la primera vez que se vio— se calcula acá.
        'Los cuatro del cuadro de {equipo_nombre} fueron dominicanos: {detalle}.'
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
        -- LA DEFENSA ES EL EQUIPO QUE NO BATEA. `batea_casa = 1` significa que el cuadro es
        -- los visitantes: es la vuelta contraria a la de los detectores de bateo.
        CASE WHEN e.batea_casa = 1 THEN g.AWAY_TEAM_ID ELSE g.HOME_TEAM_ID END AS equipo,
        CASE WHEN e.batea_casa = 1 THEN g.HOME_TEAM_ID ELSE g.AWAY_TEAM_ID END AS rival,
        CASE WHEN e.batea_casa = 1 THEN 0 ELSE 1 END AS en_casa,
        1                                         AS signo,
        4                                         AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        h3.nombre + ', ' + h4.nombre + ', ' + h5.nombre + ' y ' + h6.nombre AS detalle,
        COALESCE(eq.nombre, '')                   AS equipo_nombre,
        COALESCE(ri.nombre, '')                   AS rival_nombre,
        ''                                        AS oponente
FROM    elegido e
INNER JOIN #huella h3 ON h3.retro_id = e.p3
INNER JOIN #huella h4 ON h4.retro_id = e.p4
INNER JOIN #huella h5 ON h5.retro_id = e.p5
INNER JOIN #huella h6 ON h6.retro_id = e.p6
INNER JOIN #huella hp ON hp.mlb_id  = e.mlb_id
LEFT  JOIN #fechas f ON f.game_id = e.game_id
LEFT  JOIN dbo.retroGamesReg g ON g.GAME_ID = e.game_id
LEFT  JOIN #equipos eq ON eq.codigo = CASE WHEN e.batea_casa = 1 THEN g.AWAY_TEAM_ID ELSE g.HOME_TEAM_ID END
                      AND f.fecha BETWEEN eq.desde AND eq.hasta
LEFT  JOIN #equipos ri ON ri.codigo = CASE WHEN e.batea_casa = 1 THEN g.HOME_TEAM_ID ELSE g.AWAY_TEAM_ID END
                      AND f.fecha BETWEEN ri.desde AND ri.hasta
WHERE   f.fecha IS NOT NULL;

-- =====================================================================================
-- LA LISTA — «¿en qué juegos fue el cuadro entero dominicano?»
-- =====================================================================================
/*
WITH med AS (
    SELECT e.GAME_ID, MIN(e.POS3_FLD_ID) AS p3, MIN(e.POS4_FLD_ID) AS p4, MIN(e.POS5_FLD_ID) AS p5, MIN(e.POS6_FLD_ID) AS p6
    FROM   dbo.retroEventsReg e GROUP BY e.GAME_ID, e.INN_CT, e.BAT_HOME_ID
)
SELECT  DISTINCT CAST(g.GAME_DT AS date) AS fecha,
        n3.nameList AS primera, n4.nameList AS segunda, n5.nameList AS tercera, n6.nameList AS campocorto
FROM    med m
INNER JOIN dbo.dglMaster n3 ON n3.retroID = m.p3
INNER JOIN dbo.dglMaster n4 ON n4.retroID = m.p4
INNER JOIN dbo.dglMaster n5 ON n5.retroID = m.p5
INNER JOIN dbo.dglMaster n6 ON n6.retroID = m.p6
LEFT  JOIN dbo.retroGamesReg g ON g.GAME_ID = m.GAME_ID
ORDER BY fecha;
*/
