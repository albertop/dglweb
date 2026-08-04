-- =====================================================================================
-- EL JONRON 50 DE UNA TEMPORADA. Medido: 9 temporadas, 4 jugadores.
--
--     Sammy Sosa      1998 (66)   1999 (63)   2000 (50)   2001 (64)
--     Alex Rodriguez  2001 (52)   2002 (57)   2007 (54)
--     David Ortiz     2006 (54)
--     Jose Bautista   2010 (54)
--
-- Cincuenta es EL numero: el que separa una gran temporada de una historica. Con 40 serian 52
-- temporadas de 19 jugadores y dejaria de ser noticia.
--
-- SOLO TEMPORADA REGULAR, porque el hito ES el numero de temporada regular. El porque esta en el
-- preludio _05_temporada.sql, que es donde se calcula el acumulado.
--
-- COMO SE DETECTA EL CRUCE: el juego en que el acumulado llega al umbral y el acumulado ANTERIOR
-- todavia no habia llegado. Da UNA fila por temporada, la del dia exacto.
--
-- GRANO: juego-jugador (292.948), el mismo que los hitos de carrera.
-- =====================================================================================
SELECT  'hito_hr50' AS tipo,
        '50+ jonrones en una temporada' AS gesta,
        'bateador' AS rol,
        'completa' AS cobertura,
        288826 AS universo,
        1 AS situar,
        -- El titular dice con cuanto CERRO la temporada, que es lo que convierte «llego a 50» en
        -- «llego a 50 y termino con 66».
        'Llegó a 50 jonrones en la temporada, contra {rival_nombre}: ' +
        CASE WHEN t.hr_tot > 50
             THEN 'terminó la temporada con ' + CAST(t.hr_tot AS varchar(4)) + '.'
             ELSE 'y ahí cerró el año.' END AS plantilla,
        t.mlb_id, t.nombre, t.fecha, t.temporada, t.game_id,
        0 AS event_id,
        'R' AS game_type,
        t.equipo, t.rival, t.en_casa,
        1 AS signo,
        -- La MAGNITUD es el total de la temporada, no el acumulado al cruzar: al cruzar todos rondan
        -- el umbral y no se distinguirian entre si.
        t.hr_tot AS magnitud,
        NULL AS wpa_jugador,
        NULL AS li_max,
        CAST(t.hr_tot AS varchar(4)) AS detalle,
        t.equipo_nombre, t.rival_nombre,
        '' AS oponente
FROM    #temporada t
WHERE   t.hr_ac >= 50
  AND   (t.hr_ac - t.B_HR) < 50;

-- =====================================================================================
-- LA LISTA — las temporadas que llegaron
-- =====================================================================================
/*
SELECT  m.nameList AS jugador, r.SEASON AS temporada, SUM(r.B_HR) AS total
FROM    dbo.retroDailyReg r
INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
GROUP BY m.nameList, r.SEASON
HAVING  SUM(r.B_HR) >= 50
ORDER BY total DESC;
*/