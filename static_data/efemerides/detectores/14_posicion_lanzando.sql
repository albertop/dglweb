-- =====================================================================================
-- UN JUGADOR DE POSICIÓN SUBE A LA LOMA. Medido: 69 veces, 35 jugadores.
--
-- El campocorto lanzando el noveno de una paliza. No es una hazaña ni una deshonra: es una de las
-- estampas más queridas del béisbol, y últimamente pasa cada año.
--
-- QUIÉN ES «JUGADOR DE POSICIÓN» SE MIDE, NO SE LISTA. Un jugador entra si en TODA SU CARRERA lanzó
-- en menos del 10 % de sus juegos. Así no hace falta mantener una lista de nombres ni fiarse de una
-- etiqueta de la base: el propio expediente del hombre dice lo que era.
--
-- El corte del 10 % es holgado a propósito. Los casos reales quedan lejísimos de él:
--
--     Amed Rosario     1.016 juegos de carrera, lanzó en 1
--     Gary Sánchez       893, lanzó en 1
--     Wili Castro        713, lanzó en 6
--     Ezequiel Durán     362, lanzó en 4
--     Vidal Bruján       264, lanzó en 4
--
-- Nadie cae cerca de la frontera, así que mover el umbral al 5 % o al 15 % no cambiaría la lista. Un
-- umbral que no es sensible es un umbral bien puesto.
--
-- ES UN FENÓMENO MODERNO y el archivo lo va a reflejar solo: de las 69 veces, la enorme mayoría son
-- de la última década, desde que los equipos dejaron de gastar el bullpen en juegos perdidos.
--
-- LA CONTRAPARTE es `15_lanzador_en_posicion`, y es muchísimo más rara: solo dos veces.
--
-- GRANO: juego-jugador (292.948).
-- =====================================================================================
WITH perfil AS (
    -- El expediente de carrera de cada dominicano: cuántos juegos y en cuántos lanzó.
    SELECT  j.PLAYER_ID,
            COUNT(1) AS juegos,
            SUM(CASE WHEN j.P_G >= 1 THEN 1 ELSE 0 END) AS juegos_lanzando
    FROM    #juegos j
    GROUP BY j.PLAYER_ID
)
SELECT  'posicion_lanzando' AS tipo,
        'un juego lanzando siendo jugador de posición' AS gesta,
        'lanzador'                                AS rol,
        'completa'                                AS cobertura,
        292948                                    AS universo,
        1                                         AS situar,
        'Subió a la loma sin ser lanzador, contra {rival_nombre}: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                         AS signo,
        -- Cuantos menos juegos haya lanzado en su vida, más rara es la estampa. Se invierte para que
        -- el percentil ordene al revés: el que lanzó UNA vez en mil juegos va arriba.
        1000 - p.juegos_lanzando                  AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        CASE WHEN j.P_OUT > 0
             THEN 'sacó ' + CAST(j.P_OUT AS varchar(2))
                  + CASE WHEN j.P_OUT = 1 THEN ' out' ELSE ' outs' END
             ELSE 'no sacó un solo out' END
        + CASE WHEN j.P_SO > 0 THEN ' y ponchó a ' + CAST(j.P_SO AS varchar(2)) ELSE '' END
        + CASE WHEN p.juegos_lanzando = 1
               THEN ', la única vez que lanzó en su carrera'
               ELSE ', una de las ' + CAST(p.juegos_lanzando AS varchar(3)) + ' veces que lanzó en su carrera' END AS detalle,
        j.equipo_nombre, j.rival_nombre,
        ''                                        AS oponente
FROM    #juegos j
INNER JOIN perfil p ON p.PLAYER_ID = j.PLAYER_ID
WHERE   j.P_G >= 1
  AND   p.juegos_lanzando * 10 < p.juegos;

-- =====================================================================================
-- LA LISTA — «¿qué jugadores de posición han lanzado?»
-- =====================================================================================
/*
WITH d AS (
    SELECT r.PLAYER_ID, r.GAME_ID, r.GAME_DT, r.P_G, r.P_OUT, r.P_SO
    FROM   dbo.retroDailyReg r INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
    UNION ALL
    SELECT p.PLAYER_ID, p.GAME_ID, p.GAME_DT, p.P_G, p.P_OUT, p.P_SO
    FROM   dbo.retroDailyPost p INNER JOIN dbo.dglMaster m ON m.retroID = p.PLAYER_ID
),
perfil AS (
    SELECT PLAYER_ID, COUNT(1) AS juegos,
           SUM(CASE WHEN P_G >= 1 THEN 1 ELSE 0 END) AS lanzando
    FROM   d GROUP BY PLAYER_ID
)
SELECT  CAST(d.GAME_DT AS date) AS fecha, m.nameList AS jugador,
        pf.juegos AS juegos_carrera, pf.lanzando AS juegos_lanzando,
        d.P_OUT AS outs, d.P_SO AS ponches
FROM    d
INNER JOIN perfil pf ON pf.PLAYER_ID = d.PLAYER_ID
INNER JOIN dbo.dglMaster m ON m.retroID = d.PLAYER_ID
WHERE   d.P_G >= 1 AND pf.lanzando * 10 < pf.juegos
ORDER BY fecha DESC;
*/
