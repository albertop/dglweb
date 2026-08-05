-- =====================================================================================
-- EL QUE PONE EL SOMBRERO: un lanzador dominicano poncha CUATRO VECES al mismo bateador.
--
-- Pedido del dueño. Es el mismo hecho que `18_sombrero_mismo_lanzador` visto desde el montículo, y
-- por eso son dos detectores y no uno: allá el dominicano es la víctima, acá es el autor. El signo se
-- invierte con el punto de vista.
--
-- Medido: 25 veces, 16 lanzadores. Para verse cuatro veces con el mismo bateador hay que aguantar
-- ocho o nueve entradas, así que este detector solo lo alcanzan abridores de los que terminan lo que
-- empiezan — y la lista lo confirma:
--
--     Pedro Martínez    1997, 1999, 2000, 2002, 2003
--     José Rijo         1986 (dos veces), 1989
--     Juan Marichal     1964, 1965
--     Mario Melvin Soto, Ramón Martínez, Pedro Astacio, Juan Guzmán, Bartolo Colón…
--
-- LA MEJOR ES LA ÚLTIMA DE PEDRO: **16 de octubre de 2003, Pedro Martínez ponchó cuatro veces a
-- Alfonso Soriano** — dominicano contra dominicano, en el séptimo juego de una serie de campeonato.
--
-- CUANDO LA VÍCTIMA TAMBIÉN ES DOMINICANA el texto lo dice, igual que en
-- `65_grand_slam_vs_dominicano`: es la clase de detalle que hace la efeméride.
--
-- `signo = +1`. Dominar así a un bateador es una gesta, no una deshonra — la deshonra es de él, y esa
-- ya la publica el detector 18.
--
-- GRANO: juego-jugador (292.948).
-- =====================================================================================
WITH duelo AS (
    SELECT  e.GAME_ID, e.BATTER_ID, e.PITCHER_ID, COUNT(1) AS ponches
    FROM    dbo.r24Events e
    WHERE   e.SO = 1 AND e.GAME_TYPE = 'R'  -- solo temporada regular, ver `_00_comun.sql`
    GROUP BY e.GAME_ID, e.BATTER_ID, e.PITCHER_ID
    HAVING  COUNT(1) >= 4
)
SELECT  'sombrero_propinado' AS tipo,
        'en ponchar 4 veces al mismo bateador en un juego' AS gesta,
        '' AS participantes,
        'lanzador'                                AS rol,
        'completa'                                AS cobertura,
        288826                                    AS universo,
        1                                         AS situar,
        'Le puso el sombrero dorado a {oponente}, de {rival_nombre}: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                         AS signo,
        d.ponches                                 AS magnitud,
        NULL                                      AS wpa_jugador,
        j.li_max,
        'lo ponchó ' + CAST(d.ponches AS varchar(2)) + ' veces'
            -- Dominicano contra dominicano: el dato que convierte el hecho en historia.
            + CASE WHEN dom.retroID IS NOT NULL THEN ', y era su compatriota' ELSE '' END AS detalle,
        j.equipo_nombre, j.rival_nombre,
        COALESCE(bt.nombre, 'el mismo bateador')  AS oponente
FROM    duelo d
INNER JOIN #juegos j ON j.game_id = d.GAME_ID AND j.PLAYER_ID = d.PITCHER_ID
LEFT  JOIN #nombres bt ON bt.retro_id = d.BATTER_ID
LEFT  JOIN dbo.dglMaster dom ON dom.retroID = d.BATTER_ID;

-- =====================================================================================
-- LA LISTA — «¿qué lanzadores dominicanos poncharon cuatro veces al mismo bateador?»
-- =====================================================================================
/*
WITH duelo AS (
    SELECT e.GAME_ID, e.BATTER_ID, e.PITCHER_ID, COUNT(1) AS ponches
    FROM   dbo.r24Events e WHERE e.SO = 1
    GROUP BY e.GAME_ID, e.BATTER_ID, e.PITCHER_ID HAVING COUNT(1) >= 4
),
f AS (SELECT GAME_ID, CAST(GAME_DT AS date) AS fecha FROM dbo.retroGamesReg
      UNION ALL SELECT GAME_ID, CAST(GAME_DT AS date) FROM dbo.retroGamesPost)
SELECT  f.fecha, m.nameList AS lanzador, d.ponches,
        COALESCE(b.nameList, d.BATTER_ID) AS victima
FROM    duelo d
INNER JOIN dbo.dglMaster m ON m.retroID = d.PITCHER_ID
LEFT  JOIN dbo.dglMaster b ON b.retroID = d.BATTER_ID
LEFT  JOIN f ON f.GAME_ID = d.GAME_ID
ORDER BY f.fecha;
*/
