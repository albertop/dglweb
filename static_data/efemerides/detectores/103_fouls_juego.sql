-- =====================================================================================
-- DIECISÉIS O MÁS FOULS EN UN JUEGO. Medido: 17 juegos, 17 bateadores.
--
-- El hermano de `102_fouls_turno` en grano de juego: no es un turno interminable sino una TARDE
-- entera peleando cada lanzamiento.
--
-- EL UMBRAL, sobre los 102.228 juegos-bateador dominicanos con Statcast (2008-2026):
--
--     14 fouls   58 juegos, 41 bateadores   3,1 por temporada   <- rutina
--     15         36, 29                     1,9
--     16         17, 17                     0,9                 <- el corte
--     17          8,  8                     0,4
--     18          5,  5                     0,3                 <- el récord
--
-- Dieciséis da casi exactamente uno por temporada, el mismo criterio con que se cortaron los
-- pelotazos y el jonrón largo. Y otra vez NINGÚN BATEADOR REPITE.
--
-- SE FUSIONA CON `102_fouls_turno` cuando coinciden —un turno de once fouls arrastra el juego hacia
-- los dieciséis— y manda el del turno, que tiene más rareza. Es lo correcto: el hecho más específico
-- no puede perder contra el que lo contiene.
--
-- ⚠️ COBERTURA PARCIAL, 2008 en adelante. NO publica totales. Ver docs/EFEMERIDES.md 5.3.
--
-- GRANO: el juego-bateador con Statcast (102.228).
-- =====================================================================================
SELECT  'fouls_juego' AS tipo,
        '16+ fouls en un juego' AS gesta,
        '' AS participantes,
        'bateador'                                AS rol,
        'parcial'                                 AS cobertura,
        102228                                    AS universo,
        1                                         AS situar,
        'Bateó {detalle} contra {rival_nombre}.'  AS plantilla,
        p.mlb_id, p.nombre, p.fecha, p.temporada, p.game_id,
        0                                         AS event_id,
        p.game_type, p.equipo, p.rival, p.en_casa,
        1                                         AS signo,
        s.fouls                                   AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        CAST(s.fouls AS varchar(3)) + ' fouls en un solo juego, en '
            + CAST(s.turnos AS varchar(2))
            + CASE WHEN s.turnos = 1 THEN ' turno' ELSE ' turnos' END AS detalle,
        p.equipo_nombre, p.rival_nombre,
        ''                                        AS oponente
FROM    #puente p
INNER JOIN (
    SELECT  s.batter, CAST(s.game_date AS date) AS fecha,
            SUM(CASE WHEN s.description IN ('foul','foul_tip','foul_bunt','bunt_foul_tip')
                     THEN 1 ELSE 0 END) AS fouls,
            COUNT(DISTINCT s.at_bat_number) AS turnos
    FROM    dbo.scastPitch s
    WHERE   s.game_type = 'R'          -- solo temporada regular, ver `_00_comun.sql`
    GROUP BY s.batter, CAST(s.game_date AS date)
    HAVING  SUM(CASE WHEN s.description IN ('foul','foul_tip','foul_bunt','bunt_foul_tip')
                     THEN 1 ELSE 0 END) >= 16
) s ON s.batter = p.mlb_id AND s.fecha = p.fecha;

-- =====================================================================================
-- LA LISTA — «¿quiénes batearon más fouls en un juego?»
-- =====================================================================================
/*
SELECT  m.nameList AS bateador, CAST(s.game_date AS date) AS fecha,
        SUM(CASE WHEN s.description IN ('foul','foul_tip','foul_bunt','bunt_foul_tip') THEN 1 ELSE 0 END) AS fouls,
        COUNT(DISTINCT s.at_bat_number) AS turnos
FROM    dbo.scastPitch s
INNER JOIN dbo.dglMaster m ON m.mlbID = s.batter
WHERE   s.game_type = 'R'
GROUP BY m.nameList, CAST(s.game_date AS date)
HAVING  SUM(CASE WHEN s.description IN ('foul','foul_tip','foul_bunt','bunt_foul_tip') THEN 1 ELSE 0 END) >= 16
ORDER BY fouls DESC;
*/
