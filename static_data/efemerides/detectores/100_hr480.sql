-- =====================================================================================
-- EL JONRÓN DE 480 PIES O MÁS. Medido: 12 jonrones, 7 bateadores.
--
-- Estaba DISEÑADO DESDE EL PRINCIPIO y nunca se había construido — figuraba en la lista de la 5.12
-- del diseño junto a `vel100` y los dos de fouls. Lo reclamó el dueño el 2026-08-04.
--
-- EL UMBRAL, medido sobre los 8.413 jonrones dominicanos con distancia (2015-2026):
--
--     450 pies   245 jonrones, 64 bateadores    20,4 por temporada   <- rutina
--     460        101, 38                         8,4
--     470         33, 21                         2,8
--     480         12,  7                         1,0                 <- el corte
--     490          6,  4                         0,5
--     500          1,  1                         0,1                 <- el récord
--
-- CUATROCIENTOS OCHENTA DA EXACTAMENTE UNO POR TEMPORADA, que es el criterio con que se cortaron los
-- fouls y los pelotazos. Con 470 serían casi tres al año y dejaría de ser noticia.
--
-- EL RÉCORD DOMINICANO: **Nomar Mazara, 21 de junio de 2019, 505 pies.** Es el único que ha pasado de
-- 500. Le siguen Miguel Sanó (496 y 495), Jesús Sánchez (496) y Gary Sánchez (493).
--
-- ⚠️ COBERTURA PARCIAL: 2015 en adelante. La distancia del batazo no existe antes — Statcast la
-- empieza a medir ese año. Por eso `cobertura = 'parcial'` y el detector NO publica totales: decir
-- «uno de los 7 dominicanos» sería mentir sobre los cien años anteriores. Ver docs/EFEMERIDES.md 5.3.
--
-- GRANO: el jonrón con distancia medida (8.413). No los juegos-jugador: la oportunidad de pegar un
-- jonrón larguísimo es un jonrón, no un juego.
-- =====================================================================================
SELECT  'hr480' AS tipo,
        'un jonrón de 480 pies o más' AS gesta,
        '' AS participantes,
        'bateador'                                AS rol,
        'parcial'                                 AS cobertura,
        8413                                      AS universo,
        1                                         AS situar,
        'Conectó un jonrón de {detalle} contra {rival_nombre}.' AS plantilla,
        p.mlb_id, p.nombre, p.fecha, p.temporada, p.game_id,
        0                                         AS event_id,
        p.game_type, p.equipo, p.rival, p.en_casa,
        1                                         AS signo,
        s.pies                                    AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        CAST(s.pies AS varchar(4)) + ' pies'      AS detalle,
        p.equipo_nombre, p.rival_nombre,
        ''                                        AS oponente
FROM    #puente p
-- EL PUENTE A STATCAST ES (jugador, fecha), no el `GAME_ID`: Statcast usa el `game_pk` de MLB y
-- Retrosheet su propio identificador, y no hay tabla que los una. Ver `_03_statcast.sql`.
INNER JOIN (
    SELECT  s.batter, CAST(s.game_date AS date) AS fecha, MAX(s.hit_distance_sc) AS pies
    FROM    dbo.scastPitch s
    WHERE   s.game_type = 'R'          -- solo temporada regular, ver `_00_comun.sql`
      AND   s.events = 'home_run'
      AND   s.hit_distance_sc >= 480
    GROUP BY s.batter, CAST(s.game_date AS date)
) s ON s.batter = p.mlb_id AND s.fecha = p.fecha;

-- =====================================================================================
-- LA LISTA — «¿cuáles son los jonrones más largos de un dominicano?»
-- =====================================================================================
/*
SELECT  m.nameList AS bateador, CAST(s.game_date AS date) AS fecha,
        s.hit_distance_sc AS pies, s.launch_speed AS salida_mph, s.launch_angle AS angulo
FROM    dbo.scastPitch s
INNER JOIN dbo.dglMaster m ON m.mlbID = s.batter
WHERE   s.game_type = 'R' AND s.events = 'home_run' AND s.hit_distance_sc IS NOT NULL
ORDER BY s.hit_distance_sc DESC;
*/
