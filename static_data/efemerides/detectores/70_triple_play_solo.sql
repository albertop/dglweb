-- =====================================================================================
-- Triple play SIN ASISTENCIA: los tres outs los hace un solo fildeador.
--
-- UNO SOLO EN LA HISTORIA DOMINICANA: Rafael Furcal, 10 de agosto de 2003, campocorto, quinto
-- inning. De los 13 sin asistencia que cubre Retrosheet, uno es dominicano. Rareza 600, el tope.
--
-- `rol = fildeador`, Y ESTE DETECTOR ES LA RAZÓN DE QUE ESE CAMPO EXISTA. El contrato asumía que el
-- protagonista salía de `BATTER_ID` o `PITCHER_ID`; acá el protagonista es quien atrapó la pelota, y
-- sin `rol` la efeméride habría quedado atribuida al bateador rival — o sea, al revés.
--
-- CÓMO SE IDENTIFICA AL FILDEADOR: `PO1_FLD_CD` da la POSICIÓN que hizo el out (2-9), no el jugador.
-- El jugador sale de la columna `POS{n}_FLD_ID` que corresponde a esa posición, y por eso el CASE.
--
-- GRANO: turno al bate (822.764), que es la unidad en que puede ocurrir.
-- =====================================================================================
WITH tp AS (
    SELECT  e.GAME_ID, e.EVENT_ID, e.SEASON, e.INN_CT, e.BAT_HOME_ID, e.PO1_FLD_CD,
            CASE e.PO1_FLD_CD
                 WHEN 2 THEN e.POS2_FLD_ID WHEN 3 THEN e.POS3_FLD_ID WHEN 4 THEN e.POS4_FLD_ID
                 WHEN 5 THEN e.POS5_FLD_ID WHEN 6 THEN e.POS6_FLD_ID WHEN 7 THEN e.POS7_FLD_ID
                 WHEN 8 THEN e.POS8_FLD_ID WHEN 9 THEN e.POS9_FLD_ID END AS fildeador
    FROM    dbo.retroEventsReg e
    WHERE   e.TP_FL = 'T'
      AND   e.EVENT_OUTS_CT = 3
      AND   e.PO2_FLD_CD = e.PO1_FLD_CD          -- los tres outs
      AND   e.PO3_FLD_CD = e.PO1_FLD_CD          -- del mismo hombre
      AND   ISNULL(e.ASS1_FLD_CD, 0) = 0         -- y nadie le ayudó
)
SELECT  'triple_play_solo'                        AS tipo,
        'fildeador'                               AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        822764                                    AS universo,
        'Hizo un triple play sin asistencia contra {rival_nombre}: {detalle}.' AS plantilla,
        m.mlbID                                   AS mlb_id,
        m.nameList                                AS nombre,
        f.fecha,
        tp.SEASON                                 AS temporada,
        tp.GAME_ID                                AS game_id,
        tp.EVENT_ID                               AS event_id,
        'R'                                       AS game_type,
        -- OJO CON EL LADO: el fildeador está en el equipo que NO batea, así que `BAT_HOME_ID = 1`
        -- significa que él es el VISITANTE. Es la vuelta contraria a la de los detectores de bateo.
        CASE WHEN tp.BAT_HOME_ID = 1 THEN g.AWAY_TEAM_ID ELSE g.HOME_TEAM_ID END AS equipo,
        CASE WHEN tp.BAT_HOME_ID = 1 THEN g.HOME_TEAM_ID ELSE g.AWAY_TEAM_ID END AS rival,
        CASE WHEN tp.BAT_HOME_ID = 1 THEN 0 ELSE 1 END AS en_casa,
        1                                         AS signo,
        1                                         AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        CASE tp.PO1_FLD_CD
             WHEN 2 THEN 'de receptor' WHEN 3 THEN 'en primera' WHEN 4 THEN 'en segunda'
             WHEN 5 THEN 'en tercera'  WHEN 6 THEN 'de campocorto'
             ELSE 'en el jardín' END + ', en el ' + CASE WHEN tp.INN_CT >= 10 THEN 'inning ' + CAST(tp.INN_CT AS varchar(2)) ELSE CASE tp.INN_CT WHEN 1 THEN '1er' WHEN 2 THEN '2do' WHEN 3 THEN '3er' WHEN 4 THEN '4to' WHEN 5 THEN '5to' WHEN 6 THEN '6to' WHEN 7 THEN '7mo' WHEN 8 THEN '8vo' ELSE '9no' END END AS detalle,
        COALESCE(eq.nombre, '')                   AS equipo_nombre,
        COALESCE(ri.nombre, '')                   AS rival_nombre,
        ''                                        AS oponente
FROM    tp
INNER JOIN dbo.dglMaster m ON m.retroID = tp.fildeador
LEFT  JOIN #fechas f ON f.game_id = tp.GAME_ID
LEFT  JOIN dbo.retroGamesReg g ON g.GAME_ID = tp.GAME_ID
LEFT  JOIN #equipos eq ON eq.codigo = CASE WHEN tp.BAT_HOME_ID = 1 THEN g.AWAY_TEAM_ID ELSE g.HOME_TEAM_ID END
                      AND f.fecha BETWEEN eq.desde AND eq.hasta
LEFT  JOIN #equipos ri ON ri.codigo = CASE WHEN tp.BAT_HOME_ID = 1 THEN g.HOME_TEAM_ID ELSE g.AWAY_TEAM_ID END
                      AND f.fecha BETWEEN ri.desde AND ri.hasta;

-- =====================================================================================
-- LA LISTA — «¿quién hizo el triple play sin asistencia?»
--
-- Devuelve TODOS los de la liga, no solo el dominicano: la pregunta suele ser «¿y cuántos hay en
-- total?». Son 13 en lo que cubre Retrosheet.
-- =====================================================================================
/*
SELECT  COALESCE(dm.nameList,
                 LTRIM(RTRIM(COALESCE(NULLIF(rm.nickname,''), rm.first, '') + ' ' + COALESCE(rm.last,'')))) AS fildeador,
        CASE WHEN dm.mlbID IS NOT NULL THEN 'dominicano' ELSE '' END AS dom,
        CAST(g.GAME_DT AS date) AS fecha, e.SEASON AS temporada, e.INN_CT AS inning,
        e.PO1_FLD_CD AS posicion
FROM    dbo.retroEventsReg e
CROSS APPLY (SELECT CASE e.PO1_FLD_CD
                 WHEN 2 THEN e.POS2_FLD_ID WHEN 3 THEN e.POS3_FLD_ID WHEN 4 THEN e.POS4_FLD_ID
                 WHEN 5 THEN e.POS5_FLD_ID WHEN 6 THEN e.POS6_FLD_ID WHEN 7 THEN e.POS7_FLD_ID
                 WHEN 8 THEN e.POS8_FLD_ID WHEN 9 THEN e.POS9_FLD_ID END AS pid) x
LEFT  JOIN dbo.retroMaster rm ON rm.playerID = x.pid
LEFT  JOIN dbo.dglMaster  dm ON dm.retroID  = x.pid
LEFT  JOIN dbo.retroGamesReg g ON g.GAME_ID = e.GAME_ID
WHERE   e.TP_FL = 'T' AND e.EVENT_OUTS_CT = 3
  AND   e.PO2_FLD_CD = e.PO1_FLD_CD AND e.PO3_FLD_CD = e.PO1_FLD_CD
  AND   ISNULL(e.ASS1_FLD_CD, 0) = 0
ORDER BY g.GAME_DT;
*/
