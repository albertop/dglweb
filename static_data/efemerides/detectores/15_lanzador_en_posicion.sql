-- =====================================================================================
-- UN LANZADOR SE PARA EN OTRA POSICIÓN. Medido: DOS VECES en 116 temporadas.
--
--     1988-05-14   José De León
--     2016-06-28   Pedro Strop
--
-- Es la lista completa. La contraparte —`14_posicion_lanzando`— pasa 69 veces; esta, dos. Y la
-- asimetría tiene sentido: un manager manda al campocorto a lanzar cuando el juego ya se perdió, pero
-- poner al lanzador en el jardín obliga a rehacer la alineación entera y solo pasa en juegos larguísimos
-- o con el banco agotado.
--
-- QUIÉN ES «LANZADOR» SE MIDE, NO SE LISTA, igual que en el detector hermano y con el mismo criterio
-- al revés: entra quien en toda su carrera lanzó en MÁS del 90 % de sus juegos. Los dos casos están
-- lejos del corte —Strop 584 juegos, De León 418, los dos lanzando casi siempre— así que mover el
-- umbral no cambia nada.
--
-- NO SE CUENTA EL BATEADOR DESIGNADO ni el bateador emergente: solo las ocho posiciones defensivas de
-- verdad, `F_C_G` a `F_RF_G`. Un lanzador que va al plato en la Liga Nacional no está «jugando otra
-- posición», está bateando, y eso pasa miles de veces.
--
-- GRANO: juego-jugador (292.948).
-- =====================================================================================
WITH perfil AS (
    SELECT  j.PLAYER_ID,
            COUNT(1) AS juegos,
            SUM(CASE WHEN j.P_G >= 1 THEN 1 ELSE 0 END) AS juegos_lanzando
    FROM    #juegos j
    GROUP BY j.PLAYER_ID
),
-- Las ocho posiciones defensivas que NO son la lomita. Se toman de `retroDaily` porque `#juegos` no
-- arrastra las columnas de fildeo — no las necesitaba nadie hasta ahora.
campo AS (
    SELECT  r.PLAYER_ID, r.GAME_ID,
            r.F_C_G, r.F_1B_G, r.F_2B_G, r.F_3B_G, r.F_SS_G, r.F_LF_G, r.F_CF_G, r.F_RF_G
    FROM    dbo.retroDailyReg r

)
SELECT  'lanzador_en_posicion' AS tipo,
        'un juego jugando otra posición siendo lanzador' AS gesta,
        '' AS participantes,
        'fildeador'                               AS rol,
        'completa'                                AS cobertura,
        288826                                    AS universo,
        1                                         AS situar,
        'Siendo lanzador, jugó {detalle} contra {rival_nombre}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                         AS signo,
        1                                         AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        -- Qué posición ocupó. Se nombra la primera que aparezca: en los dos casos reales es una sola.
        CASE WHEN c.F_C_G  >= 1 THEN 'de receptor'
             WHEN c.F_1B_G >= 1 THEN 'en primera base'
             WHEN c.F_2B_G >= 1 THEN 'en segunda base'
             WHEN c.F_3B_G >= 1 THEN 'en tercera base'
             WHEN c.F_SS_G >= 1 THEN 'de campocorto'
             WHEN c.F_LF_G >= 1 THEN 'en el jardín izquierdo'
             WHEN c.F_CF_G >= 1 THEN 'en el jardín central'
             ELSE 'en el jardín derecho' END      AS detalle,
        j.equipo_nombre, j.rival_nombre,
        ''                                        AS oponente
FROM    #juegos j
INNER JOIN perfil p ON p.PLAYER_ID = j.PLAYER_ID
INNER JOIN campo  c ON c.PLAYER_ID = j.PLAYER_ID AND c.GAME_ID = j.game_id
WHERE   p.juegos_lanzando * 10 > p.juegos * 9
  AND   (c.F_C_G + c.F_1B_G + c.F_2B_G + c.F_3B_G
       + c.F_SS_G + c.F_LF_G + c.F_CF_G + c.F_RF_G) >= 1;

-- =====================================================================================
-- LA LISTA — los dos lanzadores dominicanos que jugaron otra posición
-- =====================================================================================
/*
WITH d AS (
    SELECT r.PLAYER_ID, r.GAME_ID, r.GAME_DT, r.P_G,
           r.F_C_G + r.F_1B_G + r.F_2B_G + r.F_3B_G + r.F_SS_G
         + r.F_LF_G + r.F_CF_G + r.F_RF_G AS posicion
    FROM   dbo.retroDailyReg r INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
    UNION ALL
    SELECT p.PLAYER_ID, p.GAME_ID, p.GAME_DT, p.P_G,
           p.F_C_G + p.F_1B_G + p.F_2B_G + p.F_3B_G + p.F_SS_G
         + p.F_LF_G + p.F_CF_G + p.F_RF_G
    FROM   dbo.retroDailyPost p INNER JOIN dbo.dglMaster m ON m.retroID = p.PLAYER_ID
),
perfil AS (
    SELECT PLAYER_ID, COUNT(1) AS juegos,
           SUM(CASE WHEN P_G >= 1 THEN 1 ELSE 0 END) AS lanzando
    FROM   d GROUP BY PLAYER_ID
)
SELECT  CAST(d.GAME_DT AS date) AS fecha, m.nameList AS jugador,
        pf.juegos AS juegos_carrera, pf.lanzando AS juegos_lanzando
FROM    d
INNER JOIN perfil pf ON pf.PLAYER_ID = d.PLAYER_ID
INNER JOIN dbo.dglMaster m ON m.retroID = d.PLAYER_ID
WHERE   d.posicion >= 1 AND pf.lanzando * 10 > pf.juegos * 9
ORDER BY fecha;
*/
