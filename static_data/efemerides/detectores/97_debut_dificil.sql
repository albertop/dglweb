-- =====================================================================================
-- EL DEBUT CUESTA ARRIBA: el peor primer juego de un dominicano, por VALOR DE CARRERAS.
--
-- La contraparte exacta de `96_debut_grande.sql`, mismo universo y mismo método. El umbral es -1,5:
--
--     rv <= -1,2    21 debuts
--     rv <= -1,5     9        <- el corte, simétrico al +1,5 del otro
--
-- EL PEOR DE TODOS: Rufino Linares, 10 de abril de 1981, -2,71 en cuatro turnos.
--
-- Y LA RAZÓN DE QUE ESTO VALGA LA PENA ESTÁ EN EL SEGUNDO PUESTO: **Juan Marichal, 19 de julio de
-- 1960, -1,95**. El mismo Marichal que ese día lanzó una blanqueada de UN HIT y ponchó a doce. Su
-- debut al bate fue de los peores de la historia dominicana y su debut como lanzador fue de los
-- mejores del béisbol. En la lista aparece también Miguel Tejada (1997).
--
-- ESO ES LO QUE CUENTA ESTE DETECTOR: que un mal estreno no dice nada del que viene después. Un
-- archivo de efemérides que solo publica lo bueno miente por omisión, y de todas las deshonras del
-- inventario esta es la única que termina siendo una buena noticia.
--
-- `signo = -1`: corre a media escala en todo, con techo 400. Ver docs/EFEMERIDES.md 4.5.
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
    WHERE  p.rn = 1 AND rvb.rv <= -1.5
)
SELECT  'debut_dificil'                           AS tipo,
        'un debut de -1.5 carreras de valor o peor' AS gesta,
        'bateador'                                AS rol,
        'completa'                                AS cobertura,
        288826                                    AS universo,
        1                                         AS situar,
        'Tuvo un debut cuesta arriba contra {rival_nombre}: {detalle}.'
            + CASE WHEN b.rv = (SELECT MIN(x.rv) FROM debut x)
                   THEN ' Es el debut más duro que ha tenido un dominicano.' ELSE '' END AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        -1                                        AS signo,
        -- La magnitud va en POSITIVO: el motor calcula percentiles y necesita que «más grande» sea
        -- «peor». Con el valor crudo —que acá es negativo— el orden saldría al revés.
        -b.rv                                     AS magnitud,
        NULL                                      AS wpa_jugador,
        j.li_max,
        CAST(j.B_H AS varchar(2)) + CASE WHEN j.B_H = 1 THEN ' hit' ELSE ' hits' END + ' en '
            + CAST(j.B_AB AS varchar(2)) + CASE WHEN j.B_AB = 1 THEN ' turno' ELSE ' turnos' END
            + CASE WHEN j.B_SO > 0 THEN ', con ' + CAST(j.B_SO AS varchar(2))
                        + CASE WHEN j.B_SO = 1 THEN ' ponche' ELSE ' ponches' END ELSE '' END AS detalle,
        j.equipo_nombre, j.rival_nombre,
        ''                                        AS oponente
FROM    debut b
INNER JOIN #juegos j ON j.game_id = b.GAME_ID AND j.PLAYER_ID = b.PLAYER_ID;

-- =====================================================================================
-- LA LISTA — «¿cuáles son los debuts más duros?»
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
ORDER BY rvb.rv ASC;
*/
