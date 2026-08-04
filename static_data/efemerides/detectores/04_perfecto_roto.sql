-- =====================================================================================
-- ROMPIÓ EL JUEGO PERFECTO EN EL NOVENO. Medido: 2 dominicanos.
--
--     2019-07-14   Hanser Alberto
--     2022-08-14   Jorge Mateo
--
-- Es la lista entera, y los dos lo rompieron con hit.
--
-- POR QUÉ ES UN DETECTOR APARTE DE `98_nohit_roto` (dueño, 2026-08-04). Un no-hitter se rompe con un
-- hit; un perfecto se rompe con CUALQUIER hombre en base — un boleto, un pelotazo—. Son dos gestas
-- distintas y la del perfecto es mucho más rara: de 272 no-hitters rotos en el noveno en toda la
-- liga, solo 45 eran perfectos.
--
-- SE FUSIONA CON `98_nohit_roto` cuando el batazo fue hit, que es lo que pasó en los dos casos.
-- Manda este, que tiene más rareza, y el otro queda de etiqueta — la regla de la sección 7.
--
-- ⚠️ LIMITACIÓN QUE CONVIENE DECIR: se cuenta como «hombre en base» el hit, el boleto y el pelotazo.
-- UN ERROR TAMBIÉN ROMPE UN PERFECTO y con estas columnas no se distingue, así que un perfecto roto
-- por error no lo ve este detector. No se disimula el hueco: se anota. Los dos casos dominicanos
-- fueron con hit, así que hoy no cambia nada, pero mañana podría.
--
-- GRANO: turno al bate (822.764).
-- =====================================================================================
WITH embasado AS (
    SELECT  e.GAME_ID, e.BAT_HOME_ID, e.EVENT_ID, e.INN_CT, e.OUTS_CT,
            e.BATTER_ID, e.PITCHER_ID,
            e.[1B] + e.[2B] + e.[3B] + e.HR AS hit,
            ROW_NUMBER() OVER (PARTITION BY e.GAME_ID, e.BAT_HOME_ID ORDER BY e.EVENT_ID) AS rn
    FROM    dbo.r24Events e
    WHERE   (e.[1B] + e.[2B] + e.[3B] + e.HR + e.BB + e.IBB + e.HBP) >= 1
),
roto AS (
    SELECT * FROM embasado WHERE rn = 1 AND INN_CT >= 9
)
SELECT  'perfecto_roto' AS tipo,
        'el embasado que rompió un juego perfecto en el noveno' AS gesta,
        'bateador'                                AS rol,
        'completa'                                AS cobertura,
        822764                                    AS universo,
        1                                         AS situar,
        -- El contexto va al FINAL, después de los dos puntos. Con la forma anterior —«en el {detalle},
        -- contra…»— el detalle se metía en medio y salía «en el 9no, sin outs, y fue con hit, contra
        -- Tampa Bay Rays», que se lee a tropezones.
        'Rompió el juego perfecto contra {rival_nombre}, ante {oponente}: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        r.EVENT_ID                                AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                         AS signo,
        (r.INN_CT * 3) + r.OUTS_CT                AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        'en el ' + CASE WHEN r.INN_CT = 9 THEN '9no' ELSE 'inning ' + CAST(r.INN_CT AS varchar(2)) END
            + CASE WHEN r.OUTS_CT = 2 THEN ', con 2 outs' WHEN r.OUTS_CT = 1 THEN ', con 1 out' ELSE ', sin outs' END
            + CASE WHEN r.hit >= 1 THEN ', y con hit' ELSE ', y sin batear la pelota' END AS detalle,
        j.equipo_nombre, j.rival_nombre,
        COALESCE(lz.nombre, '')                   AS oponente
FROM    roto r
INNER JOIN #juegos j ON j.game_id = r.GAME_ID AND j.PLAYER_ID = r.BATTER_ID
LEFT  JOIN #nombres lz ON lz.retro_id = r.PITCHER_ID;

-- =====================================================================================
-- LA LISTA — «¿quiénes rompieron un juego perfecto en el noveno?»
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
SELECT  f.fecha, m.nameList AS bateador, e.INN_CT AS inning, e.OUTS_CT AS outs
FROM    emb e
INNER JOIN dbo.dglMaster m ON m.retroID = e.BATTER_ID
LEFT  JOIN f ON f.GAME_ID = e.GAME_ID
WHERE   e.rn = 1 AND e.INN_CT >= 9
ORDER BY f.fecha;
*/
