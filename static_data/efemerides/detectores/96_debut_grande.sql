-- =====================================================================================
-- EL DEBUT GRANDE: el mejor primer juego de un dominicano, medido por VALOR DE CARRERAS.
--
-- Idea del dueño (2026-08-04), y es la medida correcta para esto por la misma razón que en
-- `55_paliza.sql`: un debut no se juzga por un conteo. «Dio 3 hits» no dice si fueron sencillos con
-- el juego 11-1 o el batazo que lo ganó; `RUN_VALUE` suma lo que produjo cada turno y da UNA cifra
-- comparable entre un debut de 1965 y uno de 2021.
--
-- EL UNIVERSO SON 437 DEBUTS CON TURNOS AL BATE, no los 984 del maestro: los lanzadores que
-- debutaron sin batear no entran, sencillamente porque no hay nada que medir. El rango entero va de
-- -2,71 a +3,06.
--
-- EL UMBRAL ES +1,5 carreras de valor en el juego de estreno:
--
--     rv >= 1,2    18 debuts
--     rv >= 1,5    11        <- el corte
--     rv >= 2,0     5
--
-- Once en 116 temporadas. Con 1,2 serían dieciocho y empezarían a entrar debuts meramente buenos;
-- con 2,0 quedarían cinco y se perderían estrenos que cualquiera reconocería.
--
-- EL MEJOR DE TODOS: STARLIN CASTRO, 7 de mayo de 2010 — +3,06 en cinco turnos. Le siguen Roberto
-- Peña (1965, +2,62), Miguel Andújar (2017, +2,45) y Wander Franco (2021, +2,36).
--
-- EL DEBUT ES EL PRIMER JUEGO QUE RETROSHEET LE CONOCE, no `dglMaster.debutDate`. Hace falta el
-- `GAME_ID` para poder medir los turnos, y la fecha del maestro no lo trae — además de que cuatro
-- debuts del maestro son el relleno del 1 de enero (ver `91_debut.sql`).
--
-- GRANO: juego-jugador (292.948).
-- =====================================================================================
WITH d AS (
    SELECT r.PLAYER_ID, r.GAME_ID, r.GAME_DT FROM dbo.retroDailyReg r
),
primero AS (
    SELECT  PLAYER_ID, GAME_ID,
            ROW_NUMBER() OVER (PARTITION BY PLAYER_ID ORDER BY GAME_DT, GAME_ID) AS rn
    FROM    d
),
rvb AS (
    SELECT  e.GAME_ID, e.BATTER_ID AS pid, SUM(e.RUN_VALUE) AS rv
    FROM    dbo.r24Events e WHERE e.BAT_EVENT_FL = 1 AND e.GAME_TYPE = 'R'
    GROUP BY e.GAME_ID, e.BATTER_ID
),
debut AS (
    SELECT p.PLAYER_ID, p.GAME_ID, rvb.rv
    FROM   primero p
    INNER JOIN rvb ON rvb.GAME_ID = p.GAME_ID AND rvb.pid = p.PLAYER_ID
    WHERE  p.rn = 1 AND rvb.rv >= 1.5
)
SELECT  'debut_grande'                            AS tipo,
        'un debut de 1.5+ carreras de valor' AS gesta,
        '' AS participantes,
        'bateador'                                AS rol,
        'completa'                                AS cobertura,
        288826                                    AS universo,
        1                                         AS situar,
        'Debutó en Grandes Ligas con un juegazo contra {rival_nombre}: {detalle}.'
            -- El mejor de los once se nombra como lo que es. Se calcula acá y no en el motor porque
            -- el motor ordena por fecha, no por magnitud.
            + CASE WHEN b.rv = (SELECT MAX(x.rv) FROM debut x)
                   THEN ' Es el mejor debut de un dominicano.' ELSE '' END AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                         AS signo,
        b.rv                                      AS magnitud,
        j.wpa_bat                                 AS wpa_jugador,
        j.li_max,
        CAST(j.B_H AS varchar(2)) + CASE WHEN j.B_H = 1 THEN ' hit' ELSE ' hits' END + ' en '
            + CAST(j.B_AB AS varchar(2)) + CASE WHEN j.B_AB = 1 THEN ' turno' ELSE ' turnos' END
            + CASE WHEN j.B_HR > 0 THEN ', con ' + CAST(j.B_HR AS varchar(2))
                        + CASE WHEN j.B_HR = 1 THEN ' jonrón' ELSE ' jonrones' END ELSE '' END
            + CASE WHEN j.B_RBI > 0 THEN ' y ' + CAST(j.B_RBI AS varchar(2))
                        + CASE WHEN j.B_RBI = 1 THEN ' empujada' ELSE ' empujadas' END ELSE '' END AS detalle,
        j.equipo_nombre, j.rival_nombre,
        ''                                        AS oponente
FROM    debut b
INNER JOIN #juegos j ON j.game_id = b.GAME_ID AND j.PLAYER_ID = b.PLAYER_ID;

-- =====================================================================================
-- LA LISTA — «¿cuáles son los mejores debuts dominicanos?»
-- =====================================================================================
/*
WITH d AS (
    SELECT r.PLAYER_ID, r.GAME_ID, r.GAME_DT FROM dbo.retroDailyReg r
    UNION ALL SELECT o.PLAYER_ID, o.GAME_ID, o.GAME_DT FROM dbo.retroDailyPost o
),
primero AS (SELECT PLAYER_ID, GAME_ID, GAME_DT,
            ROW_NUMBER() OVER (PARTITION BY PLAYER_ID ORDER BY GAME_DT, GAME_ID) AS rn FROM d),
rvb AS (SELECT e.GAME_ID, e.BATTER_ID AS pid, SUM(e.RUN_VALUE) AS rv, COUNT(1) AS turnos
        FROM dbo.r24Events e WHERE e.BAT_EVENT_FL = 1 GROUP BY e.GAME_ID, e.BATTER_ID)
SELECT  TOP 25 m.nameList AS jugador, CAST(p.GAME_DT AS date) AS debut,
        CAST(rvb.rv AS decimal(5,2)) AS valor_carreras, rvb.turnos
FROM    primero p
INNER JOIN dbo.dglMaster m ON m.retroID = p.PLAYER_ID
INNER JOIN rvb ON rvb.GAME_ID = p.GAME_ID AND rvb.pid = p.PLAYER_ID
WHERE   p.rn = 1
ORDER BY rvb.rv DESC;
*/
