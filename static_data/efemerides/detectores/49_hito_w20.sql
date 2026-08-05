-- =====================================================================================
-- LA VICTORIA 20 DE UNA TEMPORADA. Medido: 15 temporadas, 7 lanzadores.
--
--     Juan Marichal    1963 (25)  1964 (21)  1965 (22)  1966 (25)  1968 (26)  1969 (21)
--     Pedro Martinez   1999 (23)  2002 (20)
--     Joaquin Andujar  1984 (20)  1985 (21)
--     Bartolo Colon    2002 (20)  2005 (21)
--     Ramon Martinez   1990 (20)   Jose Lima 1999 (21)   Johnny Cueto 2014 (20)
--
-- MARICHAL SEIS VECES, y las 26 de 1968 son el techo dominicano. Veinte victorias define a un
-- abridor de elite y hoy casi se extinguio: de las 15, once son anteriores a 2003.
--
-- Con 15 serian 69 temporadas de 32 lanzadores, que es zona corriente.
--
-- SOLO TEMPORADA REGULAR, porque el hito ES el numero de temporada regular. El porque esta en el
-- preludio _05_temporada.sql, que es donde se calcula el acumulado.
--
-- COMO SE DETECTA EL CRUCE: el juego en que el acumulado llega al umbral y el acumulado ANTERIOR
-- todavia no habia llegado. Da UNA fila por temporada, la del dia exacto.
--
-- GRANO: juego-jugador (292.948), el mismo que los hitos de carrera.
-- =====================================================================================
SELECT  'hito_w20' AS tipo,
        '20+ victorias en una temporada' AS gesta,
        '' AS participantes,
        'lanzador' AS rol,
        'completa' AS cobertura,
        288826 AS universo,
        1 AS situar,
        -- El titular dice con cuanto CERRO la temporada, que es lo que convierte «llego a 50» en
        -- «llego a 50 y termino con 66».
        'Llegó a 20 victorias en la temporada, contra {rival_nombre}: ' +
        CASE WHEN t.w_tot > 20
             THEN 'terminó la temporada con ' + CAST(t.w_tot AS varchar(4)) + '.'
             ELSE 'y ahí cerró el año.' END AS plantilla,
        t.mlb_id, t.nombre, t.fecha, t.temporada, t.game_id,
        0 AS event_id,
        'R' AS game_type,
        t.equipo, t.rival, t.en_casa,
        1 AS signo,
        -- La MAGNITUD es el total de la temporada, no el acumulado al cruzar: al cruzar todos rondan
        -- el umbral y no se distinguirian entre si.
        t.w_tot AS magnitud,
        NULL AS wpa_jugador,
        NULL AS li_max,
        CAST(t.w_tot AS varchar(4)) AS detalle,
        t.equipo_nombre, t.rival_nombre,
        '' AS oponente
FROM    #temporada t
WHERE   t.w_ac >= 20
  AND   (t.w_ac - t.P_W) < 20;

-- =====================================================================================
-- LA LISTA — las temporadas que llegaron
-- =====================================================================================
/*
SELECT  m.nameList AS jugador, r.SEASON AS temporada, SUM(r.P_W) AS total
FROM    dbo.retroDailyReg r
INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
GROUP BY m.nameList, r.SEASON
HAVING  SUM(r.P_W) >= 20
ORDER BY total DESC;
*/
