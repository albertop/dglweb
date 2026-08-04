-- =====================================================================================
-- UN LANZADOR CONECTA JONRÓN. Medido: 41 veces, 24 lanzadores.
--
-- La estampa contraria a `14_posicion_lanzando`: acá el que no debería es el que batea. Y hay
-- reincidentes de lujo:
--
--     Juan Marichal      4 jonrones (1963, 1966 y dos en 1971)
--     Joaquín Andújar    3 (1979 dos veces, 1980)
--     José Sosa, Santo Alcalá, Alejandro Peña…
--
-- QUIÉN ES «LANZADOR» SE MIDE, NO SE LISTA: entra quien en toda su carrera lanzó en más del 90 % de
-- sus juegos. Mismo criterio que `15_lanzador_en_posicion`, y por la misma razón — el expediente del
-- hombre dice lo que era, sin listas de nombres que mantener.
--
-- ES UN DETECTOR QUE SE VA A SECAR SOLO, y eso está bien. El bateador designado universal llegó en
-- 2022, así que los lanzadores ya casi no van al plato: las 41 veces son casi todas del siglo pasado.
-- El archivo guarda una costumbre que se acabó, que es exactamente para lo que sirve.
--
-- GRANO: juego-jugador (292.948).
-- =====================================================================================
WITH perfil AS (
    SELECT  j.PLAYER_ID,
            COUNT(1) AS juegos,
            SUM(CASE WHEN j.P_G >= 1 THEN 1 ELSE 0 END) AS juegos_lanzando
    FROM    #juegos j
    GROUP BY j.PLAYER_ID
)
SELECT  'lanzador_jonron' AS tipo,
        'un jonrón siendo lanzador' AS gesta,
        'bateador'                                AS rol,
        'completa'                                AS cobertura,
        292948                                    AS universo,
        1                                         AS situar,
        'Conectó un jonrón siendo lanzador, contra {rival_nombre}: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                         AS signo,
        j.B_HR                                    AS magnitud,
        NULL                                      AS wpa_jugador,
        j.li_max,
        CASE WHEN j.B_HR > 1 THEN 'conectó ' + CAST(j.B_HR AS varchar(2)) + ' esa tarde'
             ELSE 'ese mismo día lanzó ' + CAST(j.P_OUT / 3 AS varchar(2))
                  + CASE WHEN j.P_OUT / 3 = 1 THEN ' entrada' ELSE ' entradas' END END
        + CASE WHEN j.B_RBI > 1 THEN ' y empujó ' + CAST(j.B_RBI AS varchar(2)) ELSE '' END AS detalle,
        j.equipo_nombre, j.rival_nombre,
        ''                                        AS oponente
FROM    #juegos j
INNER JOIN perfil p ON p.PLAYER_ID = j.PLAYER_ID
WHERE   j.B_HR >= 1
  AND   p.juegos_lanzando * 10 > p.juegos * 9;

-- =====================================================================================
-- LA LISTA — «¿qué lanzadores dominicanos han conectado jonrón?»
-- =====================================================================================
/*
WITH d AS (
    SELECT r.PLAYER_ID, r.GAME_ID, r.GAME_DT, r.P_G, r.B_HR, r.B_RBI
    FROM   dbo.retroDailyReg r INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
    UNION ALL
    SELECT p.PLAYER_ID, p.GAME_ID, p.GAME_DT, p.P_G, p.B_HR, p.B_RBI
    FROM   dbo.retroDailyPost p INNER JOIN dbo.dglMaster m ON m.retroID = p.PLAYER_ID
),
perfil AS (SELECT PLAYER_ID, COUNT(1) AS juegos,
                  SUM(CASE WHEN P_G >= 1 THEN 1 ELSE 0 END) AS lanzando
           FROM d GROUP BY PLAYER_ID)
SELECT  CAST(d.GAME_DT AS date) AS fecha, m.nameList AS lanzador,
        d.B_HR AS jonrones, d.B_RBI AS empujadas
FROM    d
INNER JOIN perfil pf ON pf.PLAYER_ID = d.PLAYER_ID
INNER JOIN dbo.dglMaster m ON m.retroID = d.PLAYER_ID
WHERE   d.B_HR >= 1 AND pf.lanzando * 10 > pf.juegos * 9
ORDER BY fecha;
*/
