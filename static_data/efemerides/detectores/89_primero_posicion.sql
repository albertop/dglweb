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
)
SELECT  'primero_posicion'                        AS tipo,
        'fildeador'                               AS rol,
        'completa'                                AS cobertura,
        0                                         AS situar,
        292948                                    AS universo,
        -- `situar = 0` porque la frase del motor sobra: el titular YA dice que fue el primero, y
        -- añadirle «fue el primer dominicano en lograrlo» sería repetirlo con otras palabras.
        'Fue el primer dominicano en abrir un juego de Grandes Ligas como {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                         AS signo,
        -- Los años transcurridos: cuanto más atrás, más historia.
        YEAR(GETDATE()) - j.temporada             AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        p.puesto                                  AS detalle,
        j.equipo_nombre, j.rival_nombre,
        ''                                        AS oponente
FROM    primeros p
INNER JOIN #juegos j ON j.game_id = p.game_id AND j.PLAYER_ID = p.pid;

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
