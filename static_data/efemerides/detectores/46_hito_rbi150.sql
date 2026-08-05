-- =====================================================================================
-- LA EMPUJADA 150 DE UNA TEMPORADA. Medido: 5 temporadas, 4 jugadores. Es la lista entera:
--
--     Manny Ramirez    1999   165   <- el techo dominicano
--     Sammy Sosa       2001   160
--     Sammy Sosa       1998   158
--     Alex Rodriguez   2007   156
--     Miguel Tejada    2004   150
--
-- Ciento cincuenta empujadas es la cifra de una temporada historica, y de los cortes medidos es el
-- unico que ademas es un numero que la gente celebra — igual que 50 jonrones, 300 ponches o 20
-- victorias. El escalon de abajo lo cubre `45_hito_rbi125`.
--
-- SOLO TEMPORADA REGULAR, porque el hito ES el numero de temporada regular. El porque esta en el
-- preludio _05_temporada.sql, que es donde se calcula el acumulado.
--
-- COMO SE DETECTA EL CRUCE: el juego en que el acumulado llega al umbral y el acumulado ANTERIOR
-- todavia no habia llegado. Da UNA fila por temporada, la del dia exacto.
--
-- GRANO: juego-jugador (292.948), el mismo que los hitos de carrera.
-- =====================================================================================
SELECT  'hito_rbi150' AS tipo,
        '150+ empujadas en una temporada' AS gesta,
        '' AS participantes,
        'bateador' AS rol,
        'completa' AS cobertura,
        288826 AS universo,
        1 AS situar,
        -- El titular dice con cuanto CERRO la temporada, que es lo que convierte «llego a 50» en
        -- «llego a 50 y termino con 66».
        'Llegó a 150 carreras empujadas en la temporada, contra {rival_nombre}: ' +
        CASE WHEN t.rbi_tot > 150
             THEN 'terminó la temporada con ' + CAST(t.rbi_tot AS varchar(4)) + '.'
             ELSE 'y ahí cerró el año.' END AS plantilla,
        t.mlb_id, t.nombre, t.fecha, t.temporada, t.game_id,
        0 AS event_id,
        'R' AS game_type,
        t.equipo, t.rival, t.en_casa,
        1 AS signo,
        -- La MAGNITUD es el total de la temporada, no el acumulado al cruzar: al cruzar todos rondan
        -- el umbral y no se distinguirian entre si.
        t.rbi_tot AS magnitud,
        NULL AS wpa_jugador,
        NULL AS li_max,
        CAST(t.rbi_tot AS varchar(4)) AS detalle,
        t.equipo_nombre, t.rival_nombre,
        '' AS oponente
FROM    #temporada t
WHERE   t.rbi_ac >= 150
  AND   (t.rbi_ac - t.B_RBI) < 150;

-- =====================================================================================
-- LA LISTA — las temporadas que llegaron
-- =====================================================================================
/*
SELECT  m.nameList AS jugador, r.SEASON AS temporada, SUM(r.B_RBI) AS total
FROM    dbo.retroDailyReg r
INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
GROUP BY m.nameList, r.SEASON
HAVING  SUM(r.B_RBI) >= 150
ORDER BY total DESC;
*/
