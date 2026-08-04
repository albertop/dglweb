-- =====================================================================================
-- LA PRIMERA VEZ QUE UN DOMINICANO ABRE UN JUEGO EN CADA POSICIÓN.
--
-- Nueve efemérides, una por puesto, y todas son historia:
--
--     1935-05-12  receptor            1957-05-08  jardín izquierdo
--     1935-07-13  campocorto          1957-05-30  jardín derecho
--     1942-08-16  jardín central      1960-07-19  LANZADOR
--     1946-04-21  segunda base        1964-05-10  primera base
--     1956-09-23  tercera base
--
-- LAS DOS DE 1935 SON DE LAS LIGAS NEGRAS, y entran con todo derecho: Retrosheet las cubre y MLB
-- las reconoce como Grandes Ligas desde 2020. Que el primer dominicano en abrir un juego lo hiciera
-- de receptor en los New York Cubans es exactamente el tipo de dato que este archivo existe para
-- rescatar.
--
-- `F_<pos>_GS` es «juegos ABIERTOS en esa posición», no jugados: un emergente que entra en el
-- séptimo no cuenta, y es lo correcto — abrir es una decisión del manager sobre quién es el titular.
--
-- GRANO: juego-jugador (292.948). Son nueve hechos irrepetibles, así que todos rondan la rareza 495.
-- Lo que los separa es la MAGNITUD: los años transcurridos desde entonces. Abrir de receptor en 1935
-- pesa más que abrir en primera en 1964, y así el orden de la lista lo pone la historia.
-- =====================================================================================
WITH d AS (
    SELECT  m.mlbID AS mlb_id, m.nameList AS nombre, r.PLAYER_ID, r.GAME_ID, CAST(r.GAME_DT AS date) AS fecha,
            r.SEASON, r.TEAM_ID, r.OPPONENT_ID, r.HOME_FL,
            r.F_P_GS, r.F_C_GS, r.F_1B_GS, r.F_2B_GS, r.F_3B_GS, r.F_SS_GS, r.F_LF_GS, r.F_CF_GS, r.F_RF_GS
    FROM    dbo.retroDailyReg r
    INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
),
-- Una fila por posición, con el juego más antiguo en que un dominicano la abrió. `TOP 1` con
-- `ORDER BY fecha, GAME_ID`: el `GAME_ID` desempata los dobles juegos del mismo día.
primeros AS (
    SELECT 'receptor'         AS puesto, 1 AS orden, (SELECT TOP 1 GAME_ID FROM d WHERE F_C_GS  >= 1 ORDER BY fecha, GAME_ID) AS game_id, (SELECT TOP 1 PLAYER_ID FROM d WHERE F_C_GS  >= 1 ORDER BY fecha, GAME_ID) AS pid
    UNION ALL SELECT 'primera base',    2, (SELECT TOP 1 GAME_ID FROM d WHERE F_1B_GS >= 1 ORDER BY fecha, GAME_ID), (SELECT TOP 1 PLAYER_ID FROM d WHERE F_1B_GS >= 1 ORDER BY fecha, GAME_ID)
    UNION ALL SELECT 'segunda base',    3, (SELECT TOP 1 GAME_ID FROM d WHERE F_2B_GS >= 1 ORDER BY fecha, GAME_ID), (SELECT TOP 1 PLAYER_ID FROM d WHERE F_2B_GS >= 1 ORDER BY fecha, GAME_ID)
    UNION ALL SELECT 'tercera base',    4, (SELECT TOP 1 GAME_ID FROM d WHERE F_3B_GS >= 1 ORDER BY fecha, GAME_ID), (SELECT TOP 1 PLAYER_ID FROM d WHERE F_3B_GS >= 1 ORDER BY fecha, GAME_ID)
    UNION ALL SELECT 'campocorto',      5, (SELECT TOP 1 GAME_ID FROM d WHERE F_SS_GS >= 1 ORDER BY fecha, GAME_ID), (SELECT TOP 1 PLAYER_ID FROM d WHERE F_SS_GS >= 1 ORDER BY fecha, GAME_ID)
    UNION ALL SELECT 'jardín izquierdo',6, (SELECT TOP 1 GAME_ID FROM d WHERE F_LF_GS >= 1 ORDER BY fecha, GAME_ID), (SELECT TOP 1 PLAYER_ID FROM d WHERE F_LF_GS >= 1 ORDER BY fecha, GAME_ID)
    UNION ALL SELECT 'jardín central',  7, (SELECT TOP 1 GAME_ID FROM d WHERE F_CF_GS >= 1 ORDER BY fecha, GAME_ID), (SELECT TOP 1 PLAYER_ID FROM d WHERE F_CF_GS >= 1 ORDER BY fecha, GAME_ID)
    UNION ALL SELECT 'jardín derecho',  8, (SELECT TOP 1 GAME_ID FROM d WHERE F_RF_GS >= 1 ORDER BY fecha, GAME_ID), (SELECT TOP 1 PLAYER_ID FROM d WHERE F_RF_GS >= 1 ORDER BY fecha, GAME_ID)
    UNION ALL SELECT 'lanzador',        9, (SELECT TOP 1 GAME_ID FROM d WHERE F_P_GS  >= 1 ORDER BY fecha, GAME_ID), (SELECT TOP 1 PLAYER_ID FROM d WHERE F_P_GS  >= 1 ORDER BY fecha, GAME_ID)
),
-- =====================================================================================
-- LOS OVERRIDES — porque a Retrosheet le faltan juegos de las Ligas Negras
-- =====================================================================================
--
-- ESTE DETECTOR NO SE PUEDE DERIVAR SOLO DE LOS DATOS, y es el único del archivo del que eso es
-- cierto. Todos los demás preguntan «¿cuántas veces pasó?», y a un conteo le faltan casos pero
-- sigue siendo honesto llamarlo «los que tenemos». Este pregunta «¿QUIÉN FUE EL PRIMERO?», y ahí un
-- hueco en la fuente no da un número bajo: da una respuesta FALSA con nombre y apellido.
--
-- Pasó exactamente eso. El detector publicaba que Horacio Martínez fue el primer dominicano en abrir
-- en el campocorto, el 13 de julio de 1935. No es cierto: fue TETELO VARGAS, el 14 de agosto de
-- 1927. La cobertura de Retrosheet de las Ligas Negras tiene huecos —de Tetelo Vargas, el juego más
-- antiguo que hay es de 1942, y solo como jardinero central— así que su temporada de 1927
-- sencillamente no está.
--
-- POR ESO ESTO ES UNA AFIRMACIÓN, NO UN CÁLCULO. El dato lo pone el dueño (2026-08-04); la consulta
-- no puede llegar a él por ningún camino. Cuando hay override, la fila NO cuelga de ningún juego:
-- se publican el hombre y la fecha, y se dejan vacíos `game_id`, equipo y rival, porque ese juego no
-- está en la base y inventarle un contexto sería repetir el error en otra columna.
--
-- Para agregar otro: una línea más acá, con el puesto tal como aparece arriba.
overrides AS (
    SELECT * FROM (VALUES
        ('campocorto', 'vargt101', CAST('1927-08-14' AS date))   -- Tetelo Vargas, no Horacio Martínez
    ) v(puesto, retro_id, fecha)
),
resuelto AS (
    SELECT  p.puesto, p.orden,
            CASE WHEN o.retro_id IS NOT NULL THEN 1 ELSE 0 END AS es_override,
            COALESCE(om.mlbID,   j.mlb_id)  AS mlb_id,
            COALESCE(om.nameList, j.nombre) AS nombre,
            COALESCE(o.fecha,    j.fecha)   AS fecha,
            -- Con override no hay juego al que apuntar: los campos de contexto van vacíos.
            CASE WHEN o.retro_id IS NOT NULL THEN '' ELSE j.game_id       END AS game_id,
            CASE WHEN o.retro_id IS NOT NULL THEN '-' ELSE j.game_type    END AS game_type,
            CASE WHEN o.retro_id IS NOT NULL THEN '' ELSE j.equipo        END AS equipo,
            CASE WHEN o.retro_id IS NOT NULL THEN '' ELSE j.rival         END AS rival,
            CASE WHEN o.retro_id IS NOT NULL THEN 0  ELSE j.en_casa       END AS en_casa,
            CASE WHEN o.retro_id IS NOT NULL THEN '' ELSE j.equipo_nombre END AS equipo_nombre,
            CASE WHEN o.retro_id IS NOT NULL THEN '' ELSE j.rival_nombre  END AS rival_nombre
    FROM    primeros p
    LEFT JOIN overrides o     ON o.puesto  = p.puesto
    LEFT JOIN dbo.dglMaster om ON om.retroID = o.retro_id
    LEFT JOIN #juegos j       ON j.game_id = p.game_id AND j.PLAYER_ID = p.pid
)
SELECT  'primero_posicion'                        AS tipo,
        'fildeador'                               AS rol,
        'completa'                                AS cobertura,
        0                                         AS situar,
        292948                                    AS universo,
        -- `situar = 0` porque la frase del motor sobra: el titular YA dice que fue el primero, y
        -- añadirle «fue el primer dominicano en lograrlo» sería repetirlo con otras palabras.
        'Fue el primer dominicano en abrir un juego de Grandes Ligas como {detalle}.' AS plantilla,
        r.mlb_id, r.nombre, r.fecha,
        YEAR(r.fecha)                             AS temporada,
        r.game_id,
        0                                         AS event_id,
        r.game_type, r.equipo, r.rival, r.en_casa,
        1                                         AS signo,
        -- Los años transcurridos: cuanto más atrás, más historia.
        YEAR(GETDATE()) - YEAR(r.fecha)           AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        r.puesto                                  AS detalle,
        r.equipo_nombre, r.rival_nombre,
        ''                                        AS oponente
FROM    resuelto r
WHERE   r.mlb_id IS NOT NULL AND r.fecha IS NOT NULL;

-- =====================================================================================
-- LA LISTA — «¿quién fue el primer dominicano en cada posición?»
-- =====================================================================================
/*
WITH d AS (
    SELECT m.nameList, CAST(r.GAME_DT AS date) AS fecha, r.TEAM_ID,
           r.F_P_GS, r.F_C_GS, r.F_1B_GS, r.F_2B_GS, r.F_3B_GS, r.F_SS_GS, r.F_LF_GS, r.F_CF_GS, r.F_RF_GS
    FROM   dbo.retroDailyReg r INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
)
SELECT 'receptor' AS puesto, (SELECT TOP 1 nameList FROM d WHERE F_C_GS >= 1 ORDER BY fecha) AS jugador, (SELECT TOP 1 fecha FROM d WHERE F_C_GS >= 1 ORDER BY fecha) AS fecha
UNION ALL SELECT 'primera base',    (SELECT TOP 1 nameList FROM d WHERE F_1B_GS >= 1 ORDER BY fecha), (SELECT TOP 1 fecha FROM d WHERE F_1B_GS >= 1 ORDER BY fecha)
UNION ALL SELECT 'segunda base',    (SELECT TOP 1 nameList FROM d WHERE F_2B_GS >= 1 ORDER BY fecha), (SELECT TOP 1 fecha FROM d WHERE F_2B_GS >= 1 ORDER BY fecha)
UNION ALL SELECT 'tercera base',    (SELECT TOP 1 nameList FROM d WHERE F_3B_GS >= 1 ORDER BY fecha), (SELECT TOP 1 fecha FROM d WHERE F_3B_GS >= 1 ORDER BY fecha)
UNION ALL SELECT 'campocorto',      (SELECT TOP 1 nameList FROM d WHERE F_SS_GS >= 1 ORDER BY fecha), (SELECT TOP 1 fecha FROM d WHERE F_SS_GS >= 1 ORDER BY fecha)
UNION ALL SELECT 'jardin izquierdo',(SELECT TOP 1 nameList FROM d WHERE F_LF_GS >= 1 ORDER BY fecha), (SELECT TOP 1 fecha FROM d WHERE F_LF_GS >= 1 ORDER BY fecha)
UNION ALL SELECT 'jardin central',  (SELECT TOP 1 nameList FROM d WHERE F_CF_GS >= 1 ORDER BY fecha), (SELECT TOP 1 fecha FROM d WHERE F_CF_GS >= 1 ORDER BY fecha)
UNION ALL SELECT 'jardin derecho',  (SELECT TOP 1 nameList FROM d WHERE F_RF_GS >= 1 ORDER BY fecha), (SELECT TOP 1 fecha FROM d WHERE F_RF_GS >= 1 ORDER BY fecha)
UNION ALL SELECT 'lanzador',        (SELECT TOP 1 nameList FROM d WHERE F_P_GS  >= 1 ORDER BY fecha), (SELECT TOP 1 fecha FROM d WHERE F_P_GS  >= 1 ORDER BY fecha)
ORDER BY fecha;
*/
