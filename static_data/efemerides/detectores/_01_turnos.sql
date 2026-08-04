-- =====================================================================================
-- EL PRELUDIO DE EVENTO: `#turnos`, un turno al bate de un dominicano con todo su contexto.
--
-- NO ES UN DETECTOR. Como `_00_comun.sql`, empieza por `_`: el motor lo corre antes que los demás y
-- no le exige el contrato.
--
-- POR QUÉ SEPARADO DEL OTRO PRELUDIO. `#juegos` sale de `retroDaily*` y su grano es el juego; esto
-- sale de `r24Events` y su grano es el TURNO. Son universos distintos —292.948 contra 822.764— y
-- mezclarlos en una tabla invitaría justo al error que la sección 5.2.11 del diseño advierte: usar
-- la `N` que no es.
--
-- LO QUE ESTA TABLA SÍ TRAE Y `#juegos` NO: el lanzador exacto. Acá el turno se enfrentó a UN
-- hombre, así que nombrarlo es verdad — al revés que en una gesta de juego completo, donde el
-- abridor no es contra quien se logró.
-- =====================================================================================

IF OBJECT_ID('tempdb..#turnos') IS NOT NULL DROP TABLE #turnos;

-- El último evento de cada juego. Es la mitad de la definición de walk-off y se calcula una sola vez
-- para los cinco detectores que lo usan.
WITH ultimo AS (
    SELECT GAME_ID, MAX(EVENT_ID) AS fin
    FROM   dbo.r24Events
    GROUP BY GAME_ID
)
SELECT  v.GAME_ID                                  AS game_id,
        v.EVENT_ID                                 AS event_id,
        m.mlbID                                    AS mlb_id,
        m.nameList                                 AS nombre,
        v.BATTER_ID                                AS retro_id,
        f.fecha,
        v.SEASON                                   AS temporada,
        v.GAME_TYPE                                AS game_type,
        v.INN_CT                                   AS inning,
        v.OUTS_CT                                  AS outs,
        v.RUNNERS                                  AS corredores,
        v.BAT_HOME_ID                              AS en_casa,
        CASE WHEN v.BAT_HOME_ID = 1 THEN v.HOME_TEAM_ID ELSE v.AWAY_TEAM_ID END AS equipo,
        CASE WHEN v.BAT_HOME_ID = 1 THEN v.AWAY_TEAM_ID ELSE v.HOME_TEAM_ID END AS rival,
        -- El marcador ANTES del turno, visto desde el equipo al bate. Es lo que permite decir
        -- «perdiendo» sin equivocarse de lado.
        CASE WHEN v.BAT_HOME_ID = 1 THEN v.HOME_SCORE_CT ELSE v.AWAY_SCORE_CT END AS sc_bat,
        CASE WHEN v.BAT_HOME_ID = 1 THEN v.AWAY_SCORE_CT ELSE v.HOME_SCORE_CT END AS sc_riv,
        -- EL WPA VA CONVERTIDO A LA VISTA DEL BATEADOR. En `r24Events` está siempre desde el equipo
        -- de CASA —medido: de 165.069 jonrones de visitantes, cero tienen WPA positivo— y esta tabla
        -- es del bateador. Sin convertir, `66_turno_clave.sql` (que pide `wpa >= 0.40`) solo podía
        -- encontrar turnos de bateadores locales: la mitad del béisbol quedaba fuera sin avisar.
        -- El porqué completo está en `_00_comun.sql`.
        CASE WHEN v.BAT_HOME_ID = 1 THEN v.WPA ELSE -v.WPA END AS wpa,
        v.LI                                       AS li,
        v.[1B] AS s1, v.[2B] AS s2, v.[3B] AS s3, v.HR AS hr,
        v.RBI AS rbi, v.BB AS bb, v.IBB AS ibb, v.HBP AS hbp, v.SO AS so,
        COALESCE(lz.nombre, '')                    AS oponente,
        -- EL retroID DEL LANZADOR, no solo su nombre. Hace falta para poder preguntar si el lanzador
        -- era dominicano, que es lo que reduce el grand slam a los duelos dominicano contra
        -- dominicano. Ver `65_grand_slam.sql`.
        v.PITCHER_ID                               AS lanzador_retro,
        -- EL WALK-OFF, y las cuatro condiciones son necesarias:
        --   último turno del juego  · el juego se acabó ahí
        --   el equipo de casa batea · el visitante no puede terminar un juego bateando
        --   noveno o más            · antes no se acaba nada
        --   WPA positivo            · lo terminó ÉL, no un error del rival
        CASE WHEN u.fin = v.EVENT_ID AND v.BAT_HOME_ID = 1 AND v.INN_CT >= 9 AND v.WPA > 0
             THEN 1 ELSE 0 END                     AS es_walkoff
INTO    #turnos
FROM    dbo.r24Events v
INNER JOIN dbo.dglMaster m ON m.retroID = v.BATTER_ID
INNER JOIN ultimo u        ON u.GAME_ID = v.GAME_ID
LEFT  JOIN #fechas  f      ON f.game_id = v.GAME_ID
LEFT  JOIN #nombres lz     ON lz.retro_id = v.PITCHER_ID
WHERE   v.BAT_EVENT_FL = 1;

CREATE CLUSTERED INDEX ix_turnos ON #turnos(game_id, event_id);

-- Los nombres de equipo se resuelven DESPUÉS, porque `#equipos` va por rango de fechas y hacerlo en
-- el SELECT de arriba obligaba a repetir el join dos veces sobre 822.764 filas.
ALTER TABLE #turnos ADD equipo_nombre varchar(60), rival_nombre varchar(60);

UPDATE t SET t.equipo_nombre = COALESCE(eq.nombre, t.equipo)
FROM   #turnos t
LEFT   JOIN #equipos eq ON eq.codigo = t.equipo AND t.fecha BETWEEN eq.desde AND eq.hasta;

UPDATE t SET t.rival_nombre = COALESCE(ri.nombre, t.rival)
FROM   #turnos t
LEFT   JOIN #equipos ri ON ri.codigo = t.rival AND t.fecha BETWEEN ri.desde AND ri.hasta;

-- --- El inning, escrito como se dice ---------------------------------------------------
-- «el 3mo» no existe en español. Se resuelve UNA vez acá en vez de repetir el CASE en los siete
-- detectores que nombran la entrada, y así tampoco hay dos formas distintas circulando.
--
-- De la décima en adelante se dice «el inning 11» y no «el 11no»: nadie narra así, y los ordinales
-- altos en español suenan a acta notarial.
ALTER TABLE #turnos ADD inning_txt varchar(20);

UPDATE #turnos SET inning_txt =
    CASE WHEN inning >= 10 THEN 'inning ' + CAST(inning AS varchar(2))
         ELSE CASE inning WHEN 1 THEN '1er' WHEN 2 THEN '2do' WHEN 3 THEN '3er'
                          WHEN 4 THEN '4to' WHEN 5 THEN '5to' WHEN 6 THEN '6to'
                          WHEN 7 THEN '7mo' WHEN 8 THEN '8vo' ELSE '9no' END
    END;
