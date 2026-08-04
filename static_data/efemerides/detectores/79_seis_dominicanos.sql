-- =====================================================================================
-- SEIS DOMINICANOS EN EL TERRENO A LA VEZ, para el mismo equipo.
--
-- Cuenta los NUEVE puestos: lanzador, receptor, el cuadro y el jardín.
--
-- SEIS ES EL RÉCORD, no un umbral elegido. Medido sobre 3,65 millones de medias entradas:
--
--     6 dominicanos     33 medias entradas    15 juegos   <- el máximo de la historia
--     5                1.066                 328
--     4               12.346               3.215
--
-- Nadie ha llegado a siete. Y el lanzador cuenta: SIN él el máximo baja a cinco, así que los seis
-- solo existen contando los nueve puestos. En el primero de todos —Chicago, 1999-06-20— los seis
-- eran lanzador, receptor, tercera, campocorto y los dos jardines.
--
-- Con cinco serían 328 juegos (2,8 por temporada) y dejaría de ser noticia. Con seis son 15 en 116
-- temporadas, y además es el techo.
--
-- GRANO: el juego-equipo (407.816 = 203.908 juegos × 2 equipos).
--
-- A QUIÉN SE LE ATRIBUYE: al de más juegos de carrera. Ver `_04_alineaciones.sql`.
-- =====================================================================================
WITH conteo AS (
    SELECT  d.game_id, d.inning, d.batea_casa,
            d.p1, d.p2, d.p3, d.p4, d.p5, d.p6, d.p7, d.p8, d.p9,
            (CASE WHEN h1.retro_id IS NOT NULL THEN 1 ELSE 0 END
           + CASE WHEN h2.retro_id IS NOT NULL THEN 1 ELSE 0 END
           + CASE WHEN h3.retro_id IS NOT NULL THEN 1 ELSE 0 END
           + CASE WHEN h4.retro_id IS NOT NULL THEN 1 ELSE 0 END
           + CASE WHEN h5.retro_id IS NOT NULL THEN 1 ELSE 0 END
           + CASE WHEN h6.retro_id IS NOT NULL THEN 1 ELSE 0 END
           + CASE WHEN h7.retro_id IS NOT NULL THEN 1 ELSE 0 END
           + CASE WHEN h8.retro_id IS NOT NULL THEN 1 ELSE 0 END
           + CASE WHEN h9.retro_id IS NOT NULL THEN 1 ELSE 0 END) AS dominicanos
    FROM    #defensa d
    LEFT JOIN #huella h1 ON h1.retro_id = d.p1
    LEFT JOIN #huella h2 ON h2.retro_id = d.p2
    LEFT JOIN #huella h3 ON h3.retro_id = d.p3
    LEFT JOIN #huella h4 ON h4.retro_id = d.p4
    LEFT JOIN #huella h5 ON h5.retro_id = d.p5
    LEFT JOIN #huella h6 ON h6.retro_id = d.p6
    LEFT JOIN #huella h7 ON h7.retro_id = d.p7
    LEFT JOIN #huella h8 ON h8.retro_id = d.p8
    LEFT JOIN #huella h9 ON h9.retro_id = d.p9
),
-- La media entrada con MÁS dominicanos de cada juego. Un juego entra una sola vez aunque la
-- formación se repita entrada tras entrada — la efeméride es del día, no de la entrada.
-- LA MEDIA ENTRADA CON MÁS DOMINICANOS DE CADA JUEGO, entera. Antes esto agregaba con MAX y se
-- quedaba solo con el número, así que la efeméride podía decir «seis dominicanos» pero no QUIÉNES:
-- los nombres se habían perdido en el GROUP BY. Con `ROW_NUMBER` se conserva la fila completa —los
-- nueve puestos— y de ahí salen los nombres. Lo pidió el dueño el 2026-08-04, y tiene razón: seis
-- nombres dominicanos en fila es la efeméride; el número solo es el titular.
mejor AS (
    SELECT  c.game_id, c.dominicanos, c.batea_casa,
            c.p1, c.p2, c.p3, c.p4, c.p5, c.p6, c.p7, c.p8, c.p9,
            ROW_NUMBER() OVER (PARTITION BY c.game_id
                               ORDER BY c.dominicanos DESC, c.inning, c.batea_casa) AS rn
    FROM    conteo c
    WHERE   c.dominicanos >= 6
),
-- El más reconocible de los que estaban en el terreno esa media entrada, y la lista de los seis.
elegido AS (
    SELECT  m.game_id, m.dominicanos, m.batea_casa,
            (SELECT TOP 1 h.mlb_id FROM #huella h
             WHERE h.retro_id IN (m.p1, m.p2, m.p3, m.p4, m.p5, m.p6, m.p7, m.p8, m.p9)
             ORDER BY h.juegos DESC, h.nombre) AS mlb_id,
            -- «A, B, C, D, E y F»: la última coma se convierte en « y », como se lee en voz alta.
            (SELECT STUFF(lista, LEN(lista) - CHARINDEX(',', REVERSE(lista)) + 1, 2, ' y ')
             FROM (SELECT STUFF((SELECT ', ' + h2.nombre
                                 FROM   #huella h2
                                 WHERE  h2.retro_id IN (m.p1, m.p2, m.p3, m.p4, m.p5,
                                                        m.p6, m.p7, m.p8, m.p9)
                                 ORDER BY h2.nombre
                                 FOR XML PATH(''), TYPE).value('.', 'nvarchar(max)'), 1, 2, '') AS lista) z
            ) AS quienes
    FROM    mejor m
    WHERE   m.rn = 1
)
SELECT  'seis_dominicanos'                        AS tipo,
        'fildeador'                               AS rol,
        'completa'                                AS cobertura,
        0                                         AS situar,
        407816                                    AS universo,
        -- `situar = 0` por lo mismo que en el jardín y el cuadro: son seis hombres, no uno.
        'Seis dominicanos a la vez en el terreno para {equipo_nombre}, contra {rival_nombre}: {detalle}.'
            + ' Es el máximo que se ha visto — nadie ha puesto siete.'
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
        -- La defensa es el equipo que NO batea.
        CASE WHEN e.batea_casa = 1 THEN g.AWAY_TEAM_ID ELSE g.HOME_TEAM_ID END AS equipo,
        CASE WHEN e.batea_casa = 1 THEN g.HOME_TEAM_ID ELSE g.AWAY_TEAM_ID END AS rival,
        CASE WHEN e.batea_casa = 1 THEN 0 ELSE 1 END AS en_casa,
        1                                         AS signo,
        e.dominicanos                             AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        e.quienes                                 AS detalle,
        COALESCE(eq.nombre, '')                   AS equipo_nombre,
        COALESCE(ri.nombre, '')                   AS rival_nombre,
        ''                                        AS oponente
FROM    elegido e
INNER JOIN #huella hp ON hp.mlb_id = e.mlb_id
LEFT  JOIN #fechas f ON f.game_id = e.game_id
LEFT  JOIN dbo.retroGamesReg g ON g.GAME_ID = e.game_id
LEFT  JOIN #equipos eq ON eq.codigo = CASE WHEN e.batea_casa = 1 THEN g.AWAY_TEAM_ID ELSE g.HOME_TEAM_ID END
                      AND f.fecha BETWEEN eq.desde AND eq.hasta
LEFT  JOIN #equipos ri ON ri.codigo = CASE WHEN e.batea_casa = 1 THEN g.HOME_TEAM_ID ELSE g.AWAY_TEAM_ID END
                      AND f.fecha BETWEEN ri.desde AND ri.hasta
WHERE   f.fecha IS NOT NULL AND e.mlb_id IS NOT NULL;

-- =====================================================================================
-- LA LISTA — «¿en qué juegos hubo seis dominicanos en el terreno?»
--
-- Devuelve además QUÉ PUESTOS ocupaban, que es la pregunta que sigue siempre.
-- =====================================================================================
/*
WITH dom AS (SELECT retroID FROM dbo.dglMaster WHERE retroID IS NOT NULL AND retroID <> ''),
med AS (
  SELECT e.GAME_ID, e.INN_CT, e.BAT_HOME_ID, MIN(e.PIT_ID) AS p1,
         MIN(e.POS2_FLD_ID) AS p2, MIN(e.POS3_FLD_ID) AS p3, MIN(e.POS4_FLD_ID) AS p4, MIN(e.POS5_FLD_ID) AS p5,
         MIN(e.POS6_FLD_ID) AS p6, MIN(e.POS7_FLD_ID) AS p7, MIN(e.POS8_FLD_ID) AS p8, MIN(e.POS9_FLD_ID) AS p9
  FROM dbo.retroEventsReg e GROUP BY e.GAME_ID, e.INN_CT, e.BAT_HOME_ID
)
SELECT DISTINCT CAST(g.GAME_DT AS date) AS fecha,
  CASE WHEN m.BAT_HOME_ID = 1 THEN g.AWAY_TEAM_ID ELSE g.HOME_TEAM_ID END AS equipo,
  CASE WHEN m.p1 IN (SELECT retroID FROM dom) THEN 'lanzador ' ELSE '' END +
  CASE WHEN m.p2 IN (SELECT retroID FROM dom) THEN 'receptor ' ELSE '' END +
  CASE WHEN m.p3 IN (SELECT retroID FROM dom) THEN '1B ' ELSE '' END +
  CASE WHEN m.p4 IN (SELECT retroID FROM dom) THEN '2B ' ELSE '' END +
  CASE WHEN m.p5 IN (SELECT retroID FROM dom) THEN '3B ' ELSE '' END +
  CASE WHEN m.p6 IN (SELECT retroID FROM dom) THEN 'SS ' ELSE '' END +
  CASE WHEN m.p7 IN (SELECT retroID FROM dom) THEN 'LF ' ELSE '' END +
  CASE WHEN m.p8 IN (SELECT retroID FROM dom) THEN 'CF ' ELSE '' END +
  CASE WHEN m.p9 IN (SELECT retroID FROM dom) THEN 'RF' ELSE '' END AS puestos
FROM med m LEFT JOIN dbo.retroGamesReg g ON g.GAME_ID = m.GAME_ID
WHERE (CASE WHEN m.p1 IN (SELECT retroID FROM dom) THEN 1 ELSE 0 END + CASE WHEN m.p2 IN (SELECT retroID FROM dom) THEN 1 ELSE 0 END
     + CASE WHEN m.p3 IN (SELECT retroID FROM dom) THEN 1 ELSE 0 END + CASE WHEN m.p4 IN (SELECT retroID FROM dom) THEN 1 ELSE 0 END
     + CASE WHEN m.p5 IN (SELECT retroID FROM dom) THEN 1 ELSE 0 END + CASE WHEN m.p6 IN (SELECT retroID FROM dom) THEN 1 ELSE 0 END
     + CASE WHEN m.p7 IN (SELECT retroID FROM dom) THEN 1 ELSE 0 END + CASE WHEN m.p8 IN (SELECT retroID FROM dom) THEN 1 ELSE 0 END
     + CASE WHEN m.p9 IN (SELECT retroID FROM dom) THEN 1 ELSE 0 END) >= 6
ORDER BY fecha;
*/
