-- =====================================================================================
-- EL PONCHE 300 DE UNA TEMPORADA. Medido: 2 temporadas, y LAS DOS SON DE PEDRO MARTINEZ.
--
--     1999   313 ponches
--     1997   305
--
-- Ningun otro dominicano ha llegado a 300. El que mas cerca estuvo es Mario Melvin Soto con 274 en
-- 1982; el propio Pedro tiene ademas 284 en 2000 y 251 en 1998.
--
-- Se queda en 300 —y no en 250, que darian 5 temporadas de 2 lanzadores— porque es la cifra redonda
-- de la categoria, la que se dice en voz alta. El escalon de abajo lo cubre `47_hito_k200`.
--
-- SOLO TEMPORADA REGULAR, porque el hito ES el numero de temporada regular. El porque esta en el
-- preludio _05_temporada.sql, que es donde se calcula el acumulado.
--
-- COMO SE DETECTA EL CRUCE: el juego en que el acumulado llega al umbral y el acumulado ANTERIOR
-- todavia no habia llegado. Da UNA fila por temporada, la del dia exacto.
--
-- GRANO: juego-jugador (292.948), el mismo que los hitos de carrera.
-- =====================================================================================
SELECT  'hito_k300' AS tipo,
        '300+ ponches en una temporada' AS gesta,
        'lanzador' AS rol,
        'completa' AS cobertura,
        288826 AS universo,
        1 AS situar,
        -- El titular dice con cuanto CERRO la temporada, que es lo que convierte «llego a 50» en
        -- «llego a 50 y termino con 66».
        'Llegó a 300 ponches en la temporada, contra {rival_nombre}: ' +
        CASE WHEN t.k_tot > 300
             THEN 'terminó la temporada con ' + CAST(t.k_tot AS varchar(4)) + '.'
             ELSE 'y ahí cerró el año.' END AS plantilla,
        t.mlb_id, t.nombre, t.fecha, t.temporada, t.game_id,
        0 AS event_id,
        'R' AS game_type,
        t.equipo, t.rival, t.en_casa,
        1 AS signo,
        -- La MAGNITUD es el total de la temporada, no el acumulado al cruzar: al cruzar todos rondan
        -- el umbral y no se distinguirian entre si.
        t.k_tot AS magnitud,
        NULL AS wpa_jugador,
        NULL AS li_max,
        CAST(t.k_tot AS varchar(4)) AS detalle,
        t.equipo_nombre, t.rival_nombre,
        '' AS oponente
FROM    #temporada t
WHERE   t.k_ac >= 300
  AND   (t.k_ac - t.P_SO) < 300;

-- =====================================================================================
-- LA LISTA — las temporadas que llegaron
-- =====================================================================================
/*
SELECT  m.nameList AS jugador, r.SEASON AS temporada, SUM(r.P_SO) AS total
FROM    dbo.retroDailyReg r
INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
GROUP BY m.nameList, r.SEASON
HAVING  SUM(r.P_SO) >= 300
ORDER BY total DESC;
*/