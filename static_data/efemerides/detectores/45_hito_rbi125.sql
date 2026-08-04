-- =====================================================================================
-- LA EMPUJADA 125 DE UNA TEMPORADA. Medido: 31 temporadas, 10 jugadores.
--
--     Alex Rodriguez   6 veces      Albert Pujols   4
--     Manny Ramirez    5            Sammy Sosa      4
--     David Ortiz      4            Vladimir Guerrero 3
--
-- EL UMBRAL SE INVESTIGO. Medido:
--
--     100+   164 temporadas de 40 jugadores   <- corriente: cuatro dominicanos por temporada
--     125+    31 de 10                        <- este detector
--     150+     5 de  4                        <- `46_hito_rbi150`
--
-- Cien es demasiado comun para ser efemeride. 125 deja una lista de treinta y una temporadas, que es
-- el tamano de `dobles3` o `extrabases4` — zona de gesta, no de rutina.
--
-- CONVIVE CON `46_hito_rbi150`: quien llega a 150 cruzo antes el 125, pero en otro juego y otro dia.
--
-- SOLO TEMPORADA REGULAR, porque el hito ES el numero de temporada regular. El porque esta en el
-- preludio _05_temporada.sql, que es donde se calcula el acumulado.
--
-- COMO SE DETECTA EL CRUCE: el juego en que el acumulado llega al umbral y el acumulado ANTERIOR
-- todavia no habia llegado. Da UNA fila por temporada, la del dia exacto.
--
-- GRANO: juego-jugador (292.948), el mismo que los hitos de carrera.
-- =====================================================================================
SELECT  'hito_rbi125' AS tipo,
        '125+ empujadas en una temporada' AS gesta,
        'bateador' AS rol,
        'completa' AS cobertura,
        292948 AS universo,
        1 AS situar,
        -- El titular dice con cuanto CERRO la temporada, que es lo que convierte «llego a 50» en
        -- «llego a 50 y termino con 66».
        'Llegó a 125 carreras empujadas en la temporada, contra {rival_nombre}: ' +
        CASE WHEN t.rbi_tot > 125
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
WHERE   t.rbi_ac >= 125
  AND   (t.rbi_ac - t.B_RBI) < 125;

-- =====================================================================================
-- LA LISTA — las temporadas que llegaron
-- =====================================================================================
/*
SELECT  m.nameList AS jugador, r.SEASON AS temporada, SUM(r.B_RBI) AS total
FROM    dbo.retroDailyReg r
INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
GROUP BY m.nameList, r.SEASON
HAVING  SUM(r.B_RBI) >= 125
ORDER BY total DESC;
*/