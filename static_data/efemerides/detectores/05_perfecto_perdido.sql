-- =====================================================================================
-- PERDIÓ EL JUEGO PERFECTO EN EL NOVENO. Medido: UNA vez.
--
-- La contraparte de `04_perfecto_roto`, desde el montículo, y la lista tiene un solo nombre. De 45
-- perfectos rotos en el noveno en toda la historia de Grandes Ligas, exactamente uno lo perdió un
-- dominicano.
--
-- `signo = +1`, por lo mismo que en `99_nohit_perdido`: llegar al noveno sin que nadie pise primera
-- no es un fallo, es haber estado a tres outs de una de las cosas más raras del béisbol. El texto
-- carga la pérdida; el puntaje carga la hazaña.
--
-- ⚠️ MISMA LIMITACIÓN QUE EL DETECTOR HERMANO: se cuenta el hit, el boleto y el pelotazo. Un error
-- rompe un perfecto y con estas columnas no se ve. Queda anotado.
--
-- SE FUSIONA CON `99_nohit_perdido` cuando el embasado fue por hit, y manda este por rareza.
--
-- GRANO: juego-jugador (292.948).
-- =====================================================================================
WITH embasado AS (
    SELECT  e.GAME_ID, e.BAT_HOME_ID, e.EVENT_ID, e.INN_CT, e.OUTS_CT,
            e.BATTER_ID, e.PITCHER_ID,
            e.[1B] + e.[2B] + e.[3B] + e.HR AS hit,
            ROW_NUMBER() OVER (PARTITION BY e.GAME_ID, e.BAT_HOME_ID ORDER BY e.EVENT_ID) AS rn
    FROM    dbo.r24Events e
    WHERE   (e.[1B] + e.[2B] + e.[3B] + e.HR + e.BB + e.IBB + e.HBP) >= 1
      AND   e.GAME_TYPE = 'R'
),
perdido AS (
    SELECT * FROM embasado WHERE rn = 1 AND INN_CT >= 9
)
SELECT  'perfecto_perdido' AS tipo,
        'un juego perfecto perdido en el noveno o más allá' AS gesta,
        '' AS participantes,
        'lanzador'                                AS rol,
        'completa'                                AS cobertura,
        288826                                    AS universo,
        1                                         AS situar,
        'Llegó al {detalle} sin que nadie le pisara primera, y lo perdió ahí: se lo quitó {oponente}, de {rival_nombre}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        p.EVENT_ID                                AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                         AS signo,
        (p.INN_CT * 3) + p.OUTS_CT                AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        CASE WHEN p.INN_CT = 9 THEN '9no inning' ELSE 'inning ' + CAST(p.INN_CT AS varchar(2)) END
            + CASE WHEN p.OUTS_CT = 2 THEN ' con 2 outs' WHEN p.OUTS_CT = 1 THEN ' con 1 out' ELSE '' END AS detalle,
        j.equipo_nombre, j.rival_nombre,
        COALESCE(bt.nombre, 'el bateador')        AS oponente
FROM    perdido p
INNER JOIN #juegos j ON j.game_id = p.GAME_ID AND j.PLAYER_ID = p.PITCHER_ID
LEFT  JOIN #nombres bt ON bt.retro_id = p.BATTER_ID;

-- =====================================================================================
-- LA LISTA — el único
-- =====================================================================================
/*
WITH emb AS (
    SELECT e.GAME_ID, e.BAT_HOME_ID, e.EVENT_ID, e.INN_CT, e.OUTS_CT, e.BATTER_ID, e.PITCHER_ID,
           ROW_NUMBER() OVER (PARTITION BY e.GAME_ID, e.BAT_HOME_ID ORDER BY e.EVENT_ID) AS rn
    FROM   dbo.r24Events e
    WHERE  (e.[1B]+e.[2B]+e.[3B]+e.HR+e.BB+e.IBB+e.HBP) >= 1
),
f AS (SELECT GAME_ID, CAST(GAME_DT AS date) AS fecha FROM dbo.retroGamesReg
      UNION ALL SELECT GAME_ID, CAST(GAME_DT AS date) FROM dbo.retroGamesPost)
SELECT  f.fecha, m.nameList AS lanzador, e.INN_CT AS inning, e.OUTS_CT AS outs
FROM    emb e
INNER JOIN dbo.dglMaster m ON m.retroID = e.PITCHER_ID
LEFT  JOIN f ON f.GAME_ID = e.GAME_ID
WHERE   e.rn = 1 AND e.INN_CT >= 9
ORDER BY f.fecha;
*/
