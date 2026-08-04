-- =====================================================================================
-- JONRÓN EN SU PRIMER TURNO EN GRANDES LIGAS.
--
-- Medido: QUINCE dominicanos, de 723 que han tenido al menos un turno. Rareza 353.
--
--     1975  José Sosa          2004  Héctor Luna        2022  Joe Dunand
--     1989  Junior Félix       2010  Starlin Castro     2022  Cristopher Morel
--     1990  José Offerman      2012  Starling Marte     2023  Jasson Domínguez
--     1999  Guillermo Mota     2018  Juan Soto          2024  Jhonkensy Noel
--     2000  Esteban Yan        2020  Sergio Alcántara
--     2002  Miguel Olivo
--
-- GRANO PROPIO Y RARO: EL JUGADOR. Cada dominicano tiene exactamente UNA oportunidad de hacer esto
-- en su vida, así que el universo no son juegos ni turnos. Es el único detector del archivo cuyo
-- universo se cuenta en personas.
--
-- Y SON 723, NO 984. La diferencia no es un descarte arbitrario, está medida:
--
--     984  en dglMaster
--     966  con retroID (los 18 que faltan son los debutantes de 2026)
--     723  CON AL MENOS UN TURNO AL BATE      <- el universo de este detector
--     237  lanzaron pero nunca batearon
--       6  ni batearon ni lanzaron
--
-- Los 237 son lanzadores que jamás tomaron un turno: el bateador designado llegó a la Liga Americana
-- en 1973 y se hizo universal en 2022. Contarlos en el denominador sería tratar como «oportunidad
-- fallida» algo que nunca pudieron intentar, y eso subestima la rareza de los que sí lo lograron.
--
-- Tres de los quince son LANZADORES —Sosa, Mota, Yan— porque en la Liga Nacional bateaban. El
-- detector no los distingue y no debe: el turno es el turno.
--
-- EL PRIMER TURNO SE ORDENA POR `fecha, game_id, event_id`, y los tres hacen falta. Sin `game_id`,
-- un debut en la primera mitad de un doble juego podría confundirse con la segunda; sin `event_id`,
-- el orden dentro del juego queda al azar.
-- =====================================================================================
WITH numerados AS (
    SELECT  t.mlb_id, t.nombre, t.fecha, t.temporada, t.game_id, t.event_id, t.game_type,
            t.equipo, t.rival, t.en_casa, t.equipo_nombre, t.rival_nombre, t.oponente,
            t.hr, t.rbi, t.wpa, t.li, t.inning_txt,
            ROW_NUMBER() OVER (PARTITION BY t.mlb_id ORDER BY t.fecha, t.game_id, t.event_id) AS turno_num
    FROM    #turnos t
)
SELECT  'hr_primer_turno'                         AS tipo,
        'un jonrón en su primer turno de Grandes Ligas' AS gesta,
        'bateador'                                AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        723                                       AS universo,
        'Debutó en Grandes Ligas con un jonrón en su primer turno, contra {rival_nombre} ante {oponente}: {detalle}.' AS plantilla,
        n.mlb_id, n.nombre, n.fecha, n.temporada, n.game_id, n.event_id, n.game_type,
        n.equipo, n.rival, n.en_casa,
        1                                         AS signo,
        -- La magnitud son las carreras que empujó: no es lo mismo estrenarse con un solitario que
        -- con uno de tres.
        n.rbi                                     AS magnitud,
        n.wpa                                     AS wpa_jugador,
        n.li                                      AS li_max,
        'en el ' + n.inning_txt
            + CASE WHEN n.rbi > 1 THEN ', y empujó ' + CAST(n.rbi AS varchar(1)) ELSE '' END AS detalle,
        n.equipo_nombre, n.rival_nombre, n.oponente
FROM    numerados n
WHERE   n.turno_num = 1
  AND   n.hr = 1;

-- =====================================================================================
-- LA LISTA — «¿quiénes debutaron con jonrón?»
--
-- Se pega tal cual y corre sola. Trae también en qué turno cayó el primer jonrón de los que NO lo
-- hicieron en el primero, porque la siguiente pregunta suele ser «¿y quién casi?».
-- =====================================================================================
/*
WITH t AS (
    SELECT v.BATTER_ID, v.GAME_ID, v.EVENT_ID, v.HR, g.fecha,
           ROW_NUMBER() OVER (PARTITION BY v.BATTER_ID ORDER BY g.fecha, v.GAME_ID, v.EVENT_ID) AS turno_num
    FROM   dbo.r24Events v
    INNER JOIN dbo.dglMaster m ON m.retroID = v.BATTER_ID
    INNER JOIN (SELECT GAME_ID, CAST(GAME_DT AS date) AS fecha FROM dbo.retroGamesReg
                UNION ALL
                SELECT GAME_ID, CAST(GAME_DT AS date) FROM dbo.retroGamesPost) g ON g.GAME_ID = v.GAME_ID
    WHERE  v.BAT_EVENT_FL = 1
)
SELECT  m.nameList AS jugador, t.fecha, t.turno_num AS en_que_turno
FROM    t
INNER JOIN dbo.dglMaster m ON m.retroID = t.BATTER_ID
WHERE   t.HR = 1
  AND   t.turno_num = (SELECT MIN(x.turno_num) FROM t x WHERE x.BATTER_ID = t.BATTER_ID AND x.HR = 1)
  AND   t.turno_num <= 5
ORDER BY t.turno_num, t.fecha;
*/
