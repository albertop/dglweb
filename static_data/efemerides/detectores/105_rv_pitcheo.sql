-- =====================================================================================
-- EL MEJOR JUEGO DESDE EL MONTÍCULO, EN CARRERAS EVITADAS. Medido: 39 juegos, 18 lanzadores.
--
-- La contraparte de `104_rv_bateo`: el `RUN_VALUE` de los turnos que enfrentó, con el signo cambiado
-- — lo que el bateador no produjo, el lanzador lo evitó.
--
-- EL UMBRAL, sobre los 288.826 juegos-jugador:
--
--     4,0 carreras   400 juegos, 69 lanzadores   3,4 por temporada   <- rutina
--     4,5            150, 44                     1,3
--     5,0             39, 18                     0,3                 <- el corte
--     5,5              3,  1
--
-- LO QUE ENCUENTRA Y NINGÚN UMBRAL DE CONTEO PODRÍA. Las mejores actuaciones son de **Juan
-- Marichal**, encabezadas por el duelo de dieciséis entradas contra Warren Spahn del 2 de julio de
-- 1963. Ese juego no fue de quince ponches ni de cero hits — fue de AGUANTAR DIECISÉIS ENTRADAS, y
-- solo lo ve una métrica que suma todo lo que pasó.
--
-- Es el mismo juego que encuentra `26_cg_extra` por el camino de las entradas. Que dos definiciones
-- independientes se topen con él es la señal de que las dos están bien escritas.
--
-- POR QUÉ EL SIGNO CAMBIADO: `RUN_VALUE` está escrito desde el bateador. Lo que para él es producir,
-- para el lanzador es permitir — así que evitar carreras es `RUN_VALUE` negativo, y se invierte para
-- que «más» siga significando «mejor».
--
-- COBERTURA COMPLETA: 1910-2025.
--
-- GRANO: juego-jugador (288.826).
-- =====================================================================================
WITH rv AS (
    SELECT  e.GAME_ID, e.PITCHER_ID, -SUM(e.RUN_VALUE) AS carreras
    FROM    dbo.r24Events e
    WHERE   e.BAT_EVENT_FL = 1
      AND   e.GAME_TYPE = 'R'          -- solo temporada regular, ver `_00_comun.sql`
    GROUP BY e.GAME_ID, e.PITCHER_ID
    HAVING  -SUM(e.RUN_VALUE) >= 5.0
)
SELECT  'rv_pitcheo' AS tipo,
        'un juego de 5+ carreras de valor evitadas' AS gesta,
        'lanzador'                                AS rol,
        'completa'                                AS cobertura,
        288826                                    AS universo,
        1                                         AS situar,
        'Evitó {detalle} contra {rival_nombre}.'  AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                         AS signo,
        rv.carreras                               AS magnitud,
        j.wpa_pit                                 AS wpa_jugador,
        j.li_max,
        CAST(CAST(rv.carreras AS decimal(4,1)) AS varchar(6)) + ' carreras de valor: '
            + CAST(j.P_OUT / 3 AS varchar(2))
            + CASE WHEN j.P_OUT / 3 = 1 THEN ' entrada' ELSE ' entradas' END
            + CASE WHEN j.P_OUT % 3 = 1 THEN ' y un tercio' WHEN j.P_OUT % 3 = 2 THEN ' y dos tercios' ELSE '' END
            + ', ' + CAST(j.P_SO AS varchar(2))
            + CASE WHEN j.P_SO = 1 THEN ' ponche' ELSE ' ponches' END
            + CASE WHEN j.P_ER = 0 THEN ' y ni una carrera limpia'
                   WHEN j.P_ER = 1 THEN ' y 1 carrera limpia'
                   ELSE ' y ' + CAST(j.P_ER AS varchar(2)) + ' limpias' END AS detalle,
        j.equipo_nombre, j.rival_nombre,
        ''                                        AS oponente
FROM    rv
INNER JOIN #juegos j ON j.game_id = rv.GAME_ID AND j.PLAYER_ID = rv.PITCHER_ID;

-- =====================================================================================
-- LA LISTA — «¿cuáles son las mejores actuaciones dominicanas desde el montículo?»
-- =====================================================================================
/*
SELECT  TOP 30 m.nameList AS lanzador, CAST(g.GAME_DT AS date) AS fecha,
        CAST(-SUM(e.RUN_VALUE) AS decimal(5,2)) AS carreras_evitadas
FROM    dbo.r24Events e
INNER JOIN dbo.dglMaster m ON m.retroID = e.PITCHER_ID
LEFT  JOIN dbo.retroGamesReg g ON g.GAME_ID = e.GAME_ID
WHERE   e.BAT_EVENT_FL = 1 AND e.GAME_TYPE = 'R'
GROUP BY m.nameList, CAST(g.GAME_DT AS date)
ORDER BY carreras_evitadas DESC;
*/
