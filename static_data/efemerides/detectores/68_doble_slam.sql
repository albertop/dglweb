-- =====================================================================================
-- DOS grand slams del mismo bateador en el mismo juego.
--
-- UNA SOLA VEZ EN LA HISTORIA DOMINICANA, y es el récord de Grandes Ligas: Fernando Tatís, 23 de
-- abril de 1999, LOS DOS EN EL MISMO INNING (el tercero), en Los Ángeles. Nadie más lo ha hecho
-- nunca, ni dominicano ni de ningún sitio.
--
-- GRANO: turno al bate (822.764). Rareza 600, el tope — pasó una vez.
--
-- La fila se cuelga del SEGUNDO slam, que es el que completa la gesta.
-- =====================================================================================
WITH dobles AS (
    SELECT  t.game_id, t.mlb_id,
            COUNT(1)          AS slams,
            MAX(t.event_id)   AS ultimo,
            MIN(t.inning)     AS inn_min,
            MAX(t.inning)     AS inn_max
    FROM    #turnos t
    WHERE   t.hr = 1 AND t.rbi = 4
    GROUP BY t.game_id, t.mlb_id
    HAVING  COUNT(1) >= 2
)
SELECT  'doble_slam'                              AS tipo,
        'dos grand slams en el mismo juego' AS gesta,
        'bateador'                                AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        822764                                    AS universo,
        'Conectó dos grand slams en el mismo juego contra {rival_nombre}: {detalle}.' AS plantilla,
        t.mlb_id, t.nombre, t.fecha, t.temporada, t.game_id, t.event_id, t.game_type,
        t.equipo, t.rival, t.en_casa,
        1                                         AS signo,
        d.slams                                   AS magnitud,
        t.wpa                                     AS wpa_jugador,
        t.li                                      AS li_max,
        -- Si los dos cayeron en la misma entrada, ESO es la noticia y no puede quedarse fuera.
        CASE WHEN d.inn_min = d.inn_max
             THEN 'los dos en el mismo inning — récord de Grandes Ligas'
             ELSE 'en los innings ' + CAST(d.inn_min AS varchar(2)) + ' y ' + CAST(d.inn_max AS varchar(2))
        END                                       AS detalle,
        t.equipo_nombre, t.rival_nombre, t.oponente
FROM    dobles d
INNER JOIN #turnos t ON t.game_id = d.game_id AND t.event_id = d.ultimo AND t.mlb_id = d.mlb_id;

-- =====================================================================================
-- LA LISTA — para cuando pregunten «¿quién fue?»
-- =====================================================================================
/*
SELECT  m.nameList AS jugador, CAST(g.GAME_DT AS date) AS fecha,
        COUNT(1) AS slams, MIN(v.INN_CT) AS primer_inning, MAX(v.INN_CT) AS ultimo_inning
FROM    dbo.r24Events v
INNER JOIN dbo.dglMaster m ON m.retroID = v.BATTER_ID
LEFT  JOIN dbo.retroGamesReg g ON g.GAME_ID = v.GAME_ID
WHERE   v.HR = 1 AND v.RBI = 4
GROUP BY m.nameList, v.GAME_ID, g.GAME_DT
HAVING  COUNT(1) >= 2
ORDER BY g.GAME_DT;
*/
