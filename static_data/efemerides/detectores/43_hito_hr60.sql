-- =====================================================================================
-- EL JONRON 60 DE UNA TEMPORADA. Medido: 3 temporadas, y LAS TRES SON DE SAMMY SOSA.
--
--     1998   66 jonrones
--     2001   64
--     1999   63
--
-- Ningun otro dominicano ha llegado a 60. Sosa es ademas el unico jugador en la historia de Grandes
-- Ligas que paso de 60 tres veces.
--
-- CONVIVE CON `42_hito_hr50` a proposito: los dos disparan sobre la misma temporada pero en JUEGOS
-- DISTINTOS —el jonron 50 y el 60 caen en fechas distintas— asi que no se fusionan y cada uno cae en
-- su propio dia del calendario. Es lo que se busca: los dos son noticia.
--
-- SOLO TEMPORADA REGULAR, porque el hito ES el numero de temporada regular. El porque esta en el
-- preludio _05_temporada.sql, que es donde se calcula el acumulado.
--
-- COMO SE DETECTA EL CRUCE: el juego en que el acumulado llega al umbral y el acumulado ANTERIOR
-- todavia no habia llegado. Da UNA fila por temporada, la del dia exacto.
--
-- GRANO: juego-jugador (292.948), el mismo que los hitos de carrera.
-- =====================================================================================
SELECT  'hito_hr60' AS tipo,
        '60+ jonrones en una temporada' AS gesta,
        'bateador' AS rol,
        'completa' AS cobertura,
        292948 AS universo,
        1 AS situar,
        -- El titular dice con cuanto CERRO la temporada, que es lo que convierte «llego a 50» en
        -- «llego a 50 y termino con 66».
        'Llegó a 60 jonrones en la temporada, contra {rival_nombre}: ' +
        CASE WHEN t.hr_tot > 60
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
WHERE   t.hr_ac >= 60
  AND   (t.hr_ac - t.B_HR) < 60;

-- =====================================================================================
-- LA LISTA — las temporadas que llegaron
-- =====================================================================================
/*
SELECT  m.nameList AS jugador, r.SEASON AS temporada, SUM(r.B_HR) AS total
FROM    dbo.retroDailyReg r
INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
GROUP BY m.nameList, r.SEASON
HAVING  SUM(r.B_HR) >= 60
ORDER BY total DESC;
*/