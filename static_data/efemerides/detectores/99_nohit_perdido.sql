-- =====================================================================================
-- PERDIÓ EL NO-HITTER EN EL NOVENO. Medido: 15 veces, 11 lanzadores.
--
-- La otra cara de `98_nohit_roto.sql`: el lanzador que llegó al noveno sin permitir un hit y lo
-- perdió ahí mismo. Mismo hecho, visto desde el montículo.
--
-- `signo = +1`, Y ESTO SE PENSÓ. Lo obvio sería marcarlo como deshonra —se perdió algo— pero eso
-- sería leer el hecho al revés: llegar al noveno sin permitir un hit lo hacen quince dominicanos en
-- 116 temporadas, y la escala negativa (4.5) lo hundiría a un techo de 400. Lo que pasó no es que
-- falló: es que estuvo a tres outs de la inmortalidad. El texto carga la pérdida; el puntaje carga
-- la hazaña.
--
-- LA LISTA ES DE LUJO Y ESO CONFIRMA EL CRITERIO:
--
--     1971-04-16   Juan Marichal
--     1994-04-13   Pedro Martínez
--     1995-06-03   Pedro Martínez, EN EL INNING 10   <- nueve entradas perfectas en Montreal
--     2000-08-29   Pedro Martínez
--
-- Pedro Martínez lo perdió TRES VECES, y la de 1995 la perdió después del noveno: había retirado a
-- los veintisiete. Un detector que marcara esto como deshonra pondría ese juego por debajo de un
-- sombrero dorado.
--
-- POR QUÉ EL LANZADOR ES EL DEL EVENTO y no forzosamente el abridor: si un relevista entra en el
-- noveno con el no-hitter vivo y lo pierde, es él quien lo perdió. Se le atribuye a quien estaba en
-- la lomita, que es como lo cuenta la crónica.
--
-- GRANO: juego-jugador (292.948).
-- =====================================================================================
WITH hits AS (
    SELECT  e.GAME_ID, e.BAT_HOME_ID, e.EVENT_ID, e.INN_CT, e.OUTS_CT, e.BATTER_ID, e.PITCHER_ID,
            ROW_NUMBER() OVER (PARTITION BY e.GAME_ID, e.BAT_HOME_ID ORDER BY e.EVENT_ID) AS rn
    FROM    dbo.r24Events e
    WHERE   (e.[1B] + e.[2B] + e.[3B] + e.HR) >= 1
),
perdido AS (
    SELECT * FROM hits WHERE rn = 1 AND INN_CT >= 9
)
SELECT  'nohit_perdido'                           AS tipo,
        -- «o más allá» porque uno de los quince se perdió en el inning 11 y otro en el 10: la gesta
        -- es la categoría, y decir solo «en el noveno» la dejaría mintiendo en esos dos.
        'un no-hitter perdido en el noveno o más allá' AS gesta,
        'lanzador'                                AS rol,
        'completa'                                AS cobertura,
        292948                                    AS universo,
        1                                         AS situar,
        'Llegó al {detalle} sin permitir un hit, y lo perdió ahí: se lo quitó {oponente}, de {rival_nombre}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        p.EVENT_ID                                AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                         AS signo,
        -- Cuanto más lejos llegó, más grande fue lo que se le escapó.
        (p.INN_CT * 3) + p.OUTS_CT                AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        CASE WHEN p.INN_CT = 9 THEN '9no' ELSE 'inning ' + CAST(p.INN_CT AS varchar(2)) END
            + CASE WHEN p.OUTS_CT = 2 THEN ' con 2 outs' WHEN p.OUTS_CT = 1 THEN ' con 1 out' ELSE '' END AS detalle,
        j.equipo_nombre, j.rival_nombre,
        COALESCE(bt.nombre, 'el bateador')        AS oponente
FROM    perdido p
INNER JOIN #juegos j ON j.game_id = p.GAME_ID AND j.PLAYER_ID = p.PITCHER_ID
LEFT  JOIN #nombres bt ON bt.retro_id = p.BATTER_ID;

-- =====================================================================================
-- LA LISTA — «¿quiénes perdieron un no-hitter en el noveno?»
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
SELECT  f.fecha, m.nameList AS lanzador, h.INN_CT AS inning, h.OUTS_CT AS outs,
        COALESCE(b.nameList, h.BATTER_ID) AS se_lo_quito
FROM    hits h
INNER JOIN dbo.dglMaster m ON m.retroID = h.PITCHER_ID
LEFT  JOIN dbo.dglMaster b ON b.retroID = h.BATTER_ID
LEFT  JOIN fechas f ON f.GAME_ID = h.GAME_ID
WHERE   h.rn = 1 AND h.INN_CT >= 9
ORDER BY f.fecha;
*/
