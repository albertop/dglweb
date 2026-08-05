-- =====================================================================================
-- LAS RECTAS DE 100 MILLAS: quince o más en un mismo juego. Medido: 37 juegos, 12 lanzadores.
--
-- Estaba diseñado desde el principio y nunca se había construido — figuraba en la lista de la 5.12
-- del diseño. Lo reclamó el dueño el 2026-08-04.
--
-- EL UMBRAL, sobre los 41.785 juegos-lanzador dominicanos con Statcast (2008-2026):
--
--     10 rectas de 100+   170 juegos, 27 lanzadores   8,9 por temporada   <- rutina
--     15                   37, 12                     1,9                 <- el corte
--     20                    5,  4                     0,3
--
-- Quince deja el detector en la liga de `hits5` y `k12`, que es donde vive el inventario. Con veinte
-- quedarían cinco juegos: pieza de museo, no efeméride recurrente.
--
-- EL RÉCORD SON VEINTIDÓS, y lo comparten **Mauricio Cabrera (2016-08-16) y Jhoan Durán
-- (2023-06-21)**. Durán además tiene el tercero, con 21.
--
-- OJO CON UN CAMBIO RESPECTO AL DISEÑO ORIGINAL: aquella lista daba el récord a Yordano Ventura con
-- 26 el 3 de octubre de 2014 — pero ese juego era de POSTEMPORADA, y el archivo ya no la mira (2.6).
-- El récord de temporada regular es 22.
--
-- ⚠️ COBERTURA PARCIAL, 2008 en adelante: es cuando Statcast empieza a medir la velocidad. NO publica
-- totales — decir «uno de los 12 dominicanos» sería mentir sobre los cien años anteriores, donde
-- nadie sabe cuántas rectas de 100 se tiraron. Ver docs/EFEMERIDES.md 5.3.
--
-- EL PUENTE A STATCAST ES (jugador, fecha) y no el `GAME_ID`: Statcast usa el `game_pk` de MLB y
-- Retrosheet su propio identificador, y no hay tabla que los una. Ver `_03_statcast.sql`.
--
-- GRANO: el juego-lanzador con Statcast (41.785).
-- =====================================================================================
SELECT  'vel100' AS tipo,
        '15+ rectas de 100 millas en un juego' AS gesta,
        '' AS participantes,
        'lanzador'                                AS rol,
        'parcial'                                 AS cobertura,
        41785                                     AS universo,
        1                                         AS situar,
        'Tiró {detalle} contra {rival_nombre}.'   AS plantilla,
        p.mlb_id, p.nombre, p.fecha, p.temporada, p.game_id,
        0                                         AS event_id,
        p.game_type, p.equipo, p.rival, p.en_casa,
        1                                         AS signo,
        s.cien                                    AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        CAST(s.cien AS varchar(3)) + ' rectas de 100 millas o más'
            + CASE WHEN s.tope >= 103 THEN ', y la más rápida llegó a '
                        + CAST(CAST(s.tope AS decimal(4,1)) AS varchar(6)) + ' mph'
                   ELSE '' END                    AS detalle,
        p.equipo_nombre, p.rival_nombre,
        ''                                        AS oponente
FROM    #puente p
INNER JOIN (
    SELECT  s.pitcher, CAST(s.game_date AS date) AS fecha,
            SUM(CASE WHEN s.release_speed >= 100 THEN 1 ELSE 0 END) AS cien,
            MAX(s.release_speed) AS tope
    FROM    dbo.scastPitch s
    WHERE   s.game_type = 'R'          -- solo temporada regular, ver `_00_comun.sql`
    GROUP BY s.pitcher, CAST(s.game_date AS date)
    HAVING  SUM(CASE WHEN s.release_speed >= 100 THEN 1 ELSE 0 END) >= 15
) s ON s.pitcher = p.mlb_id AND s.fecha = p.fecha;

-- =====================================================================================
-- LA LISTA — «¿quiénes tiran más rectas de 100 millas?»
-- =====================================================================================
/*
SELECT  m.nameList AS lanzador, CAST(s.game_date AS date) AS fecha,
        SUM(CASE WHEN s.release_speed >= 100 THEN 1 ELSE 0 END) AS rectas_de_100,
        MAX(s.release_speed) AS la_mas_rapida
FROM    dbo.scastPitch s
INNER JOIN dbo.dglMaster m ON m.mlbID = s.pitcher
WHERE   s.game_type = 'R'
GROUP BY m.nameList, CAST(s.game_date AS date)
HAVING  SUM(CASE WHEN s.release_speed >= 100 THEN 1 ELSE 0 END) >= 15
ORDER BY rectas_de_100 DESC;
*/
