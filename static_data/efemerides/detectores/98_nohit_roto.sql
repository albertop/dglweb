-- =====================================================================================
-- ROMPIÓ EL NO-HITTER EN EL NOVENO. Medido: 13 veces, 12 bateadores.
--
-- Pedido del dueño (2026-08-04). El bateador que da el PRIMER HIT del juego cuando ya se llegó al
-- noveno: hasta ese swing el rival llevaba un juego sin hits.
--
-- CÓMO SE DETECTA. Por cada juego y cada lado ofensivo se busca el primer evento con hit —sencillo,
-- doble, triple o jonrón— y se mira en qué entrada cayó. Si fue en la novena o más allá, el equipo
-- que lanzaba llevaba el no-hitter intacto hasta el octavo completo. No hace falta reconstruir nada
-- más: la definición ES el primer hit.
--
-- En toda la liga ha pasado 272 veces. De esas, 13 las rompió un dominicano.
--
-- LA HISTORIA QUE JUSTIFICA EL DETECTOR: **Nelson Liriano lo hizo DOS VECES EN CINCO DÍAS** —el 23 y
-- el 28 de abril de 1989—. Dos lanzadores distintos llegaron al noveno sin permitir un hit esa
-- semana y el mismo dominicano se los quitó a los dos. Eso no lo encuentra ningún detector de
-- conteo: no es un hit grande, es un hit en el único momento en que un sencillo es noticia mundial.
--
-- También están César Gerónimo (1976), Juan Samuel (1987), Julio César Franco (1988), Robinson Canó
-- (2006), Juan Uribe (2011), Melky Cabrera (2017) y Jorge Mateo (2022).
--
-- GRANO: turno al bate (822.764).
-- =====================================================================================
WITH hits AS (
    SELECT  e.GAME_ID, e.BAT_HOME_ID, e.EVENT_ID, e.INN_CT, e.OUTS_CT, e.BATTER_ID, e.PITCHER_ID,
            (e.[1B] + e.[2B] + e.[3B] + e.HR) AS es_hit,
            e.HR, e.RBI,
            ROW_NUMBER() OVER (PARTITION BY e.GAME_ID, e.BAT_HOME_ID ORDER BY e.EVENT_ID) AS rn
    FROM    dbo.r24Events e
    WHERE   (e.[1B] + e.[2B] + e.[3B] + e.HR) >= 1
),
roto AS (
    SELECT * FROM hits WHERE rn = 1 AND INN_CT >= 9
)
SELECT  'nohit_roto'                              AS tipo,
        'en romper un no-hitter en el noveno' AS gesta,
        'bateador'                                AS rol,
        'completa'                                AS cobertura,
        822764                                    AS universo,
        1                                         AS situar,
        'Rompió el no-hitter en el {detalle}, contra {rival_nombre} ante {oponente}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        r.EVENT_ID                                AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                         AS signo,
        -- Cuanto más tarde y con más outs, más cerca estuvo el otro de conseguirlo.
        (r.INN_CT * 3) + r.OUTS_CT                AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        CASE WHEN r.INN_CT = 9 THEN '9no' ELSE 'inning ' + CAST(r.INN_CT AS varchar(2)) END
            + CASE WHEN r.OUTS_CT = 2 THEN ', con 2 outs' WHEN r.OUTS_CT = 1 THEN ', con 1 out' ELSE ', sin outs' END
            + CASE WHEN r.HR = 1 THEN ', y fue jonrón' ELSE '' END AS detalle,
        j.equipo_nombre, j.rival_nombre,
        COALESCE(lz.nombre, '')                   AS oponente
FROM    roto r
INNER JOIN #juegos j ON j.game_id = r.GAME_ID AND j.PLAYER_ID = r.BATTER_ID
LEFT  JOIN #nombres lz ON lz.retro_id = r.PITCHER_ID;

-- =====================================================================================
-- LA LISTA — «¿quiénes rompieron un no-hitter en el noveno?»
-- =====================================================================================
/*
WITH hits AS (
    SELECT e.GAME_ID, e.BAT_HOME_ID, e.EVENT_ID, e.INN_CT, e.OUTS_CT, e.BATTER_ID, e.PITCHER_ID,
           ROW_NUMBER() OVER (PARTITION BY e.GAME_ID, e.BAT_HOME_ID ORDER BY e.EVENT_ID) AS rn
    FROM   dbo.r24Events e WHERE (e.[1B] + e.[2B] + e.[3B] + e.HR) >= 1
),
fechas AS (
    SELECT GAME_ID, CAST(GAME_DT AS date) AS fecha FROM dbo.retroGamesReg
    UNION ALL SELECT GAME_ID, CAST(GAME_DT AS date) FROM dbo.retroGamesPost
)
SELECT  f.fecha, m.nameList AS bateador, h.INN_CT AS inning, h.OUTS_CT AS outs,
        p.nameList AS le_lanzaba
FROM    hits h
INNER JOIN dbo.dglMaster m ON m.retroID = h.BATTER_ID
LEFT  JOIN dbo.dglMaster p ON p.retroID = h.PITCHER_ID
LEFT  JOIN fechas f ON f.GAME_ID = h.GAME_ID
WHERE   h.rn = 1 AND h.INN_CT >= 9
ORDER BY f.fecha;
*/
