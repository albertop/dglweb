-- =====================================================================================
-- EL PONCHE 200 DE UNA TEMPORADA. Medido: 46 temporadas, 23 lanzadores.
--
--     Pedro Martinez     9 veces      Mario Melvin Soto   3
--     Juan Marichal      6            Francisco Liriano   2
--     Freddy Peralta     3            Bartolo Colon       2
--
-- Doscientos ponches es la marca del abridor dominante de una temporada. Con 220 quedarian 18
-- temporadas de 8 lanzadores y se perderia la mitad de la lista.
--
-- SOLO TEMPORADA REGULAR, porque el hito ES el numero de temporada regular. El porque esta en el
-- preludio _05_temporada.sql, que es donde se calcula el acumulado.
--
-- COMO SE DETECTA EL CRUCE: el juego en que el acumulado llega al umbral y el acumulado ANTERIOR
-- todavia no habia llegado. Da UNA fila por temporada, la del dia exacto.
--
-- GRANO: juego-jugador (292.948), el mismo que los hitos de carrera.
-- =====================================================================================
SELECT  'hito_k200' AS tipo,
        '200+ ponches en una temporada' AS gesta,
        'lanzador' AS rol,
        'completa' AS cobertura,
        292948 AS universo,
        1 AS situar,
        -- El titular dice con cuanto CERRO la temporada, que es lo que convierte «llego a 50» en
        -- «llego a 50 y termino con 66».
        'Llegó a 200 ponches en la temporada, contra {rival_nombre}: ' +
        CASE WHEN t.k_tot > 200
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
WHERE   t.k_ac >= 200
  AND   (t.k_ac - t.P_SO) < 200;

-- =====================================================================================
-- LA LISTA — las temporadas que llegaron
-- =====================================================================================
/*
SELECT  m.nameList AS jugador, r.SEASON AS temporada, SUM(r.P_SO) AS total
FROM    dbo.retroDailyReg r
INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
GROUP BY m.nameList, r.SEASON
HAVING  SUM(r.P_SO) >= 200
ORDER BY total DESC;
*/