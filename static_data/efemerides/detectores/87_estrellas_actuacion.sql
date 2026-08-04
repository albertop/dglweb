-- =====================================================================================
-- ACTUACIÓN EN EL JUEGO DE ESTRELLAS.
--
-- Solo cuando HIZO algo: jonrón, dos o más hits, ganó el juego o lo salvó. Son 32.
--
-- POR QUÉ NO SE DETECTA LA SIMPLE ASISTENCIA, que serían 283 de 111 jugadores. Porque el Juego de
-- Estrellas es SIEMPRE EN JULIO: medido, las 283 apariciones caben en 18 días del calendario, y el
-- 13 de julio solo se llevaría 43. Un detector de asistencia convertiría esos dieciocho días en un
-- muro de nombres sin contenido, y encima desplazaría gestas reales de esas mismas fechas.
--
-- Con la actuación quedan 32, repartidas, y cada una se lee sola:
--
--     1962-07-10  Juan Marichal ganó       2007-07-10  José Reyes, 3 hits
--     1976-07-13  César Cedeño, jonrón     2021-07-13  Vladimir Guerrero Jr., jonrón
--     2004-07-13  David Ortiz, jonrón      2022-07-19  Emmanuel Clase salvó
--
-- LO QUE SE PIERDE Y DÓNDE VA. Sin detector de asistencia se pierden dos cosas:
--
--   * El PRIMER dominicano en un Juego de Estrellas —Felipe Alou y Juan Marichal, los dos el
--     1962-07-10—. Pero ese día queda cubierto igual, porque Marichal GANÓ ese mismo juego.
--   * Los que fueron muchas veces: Alex Rodríguez 11, Albert Pujols 10, Vladimir Guerrero y David
--     Ortiz 9. Eso no es una efeméride diaria sino un dato de la ficha del jugador, que es otro
--     archivo.
--
-- GRANO: el juego-jugador de estrellas (283 apariciones dominicanas). Universo propio y pequeño,
-- como manda la regla del grano — comparar 32 contra los 292.948 juegos de temporada regular diría
-- que es rarísimo, y no: es raro DENTRO del Juego de Estrellas, que es donde ocurre.
-- =====================================================================================
SELECT  'estrellas_actuacion'                     AS tipo,
        'una actuación destacada en el Juego de Estrellas' AS gesta,
        CASE WHEN a.P_OUT > 0 THEN 'lanzador' ELSE 'bateador' END AS rol,
        'completa'                                AS cobertura,
        1                                         AS situar,
        283                                       AS universo,
        'Se lució en el Juego de Estrellas: {detalle}.' AS plantilla,
        m.mlbID                                   AS mlb_id,
        m.nameList                                AS nombre,
        CAST(a.GAME_DT AS date)                   AS fecha,
        a.SEASON                                  AS temporada,
        a.GAME_ID                                 AS game_id,
        0                                         AS event_id,
        'A'                                       AS game_type,
        a.TEAM_ID                                 AS equipo,
        a.OPPONENT_ID                             AS rival,
        a.HOME_FL                                 AS en_casa,
        1                                         AS signo,
        -- Lo que pesa cada actuación. El jonrón manda, después ganar o salvar, después los hits.
        (a.B_HR * 4) + (a.P_W * 3) + (a.P_SV * 3) + a.B_H AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        -- Se arma con lo que de verdad hizo, sin dejar huecos ni comas sueltas.
        STUFF(
            CASE WHEN a.B_HR >= 1 THEN ', ' + CASE WHEN a.B_HR = 1 THEN 'jonrón' ELSE CAST(a.B_HR AS varchar(1)) + ' jonrones' END ELSE '' END
          + CASE WHEN a.B_H  >= 2 THEN ', ' + CAST(a.B_H AS varchar(1)) + ' hits' ELSE '' END
          + CASE WHEN a.P_W  >= 1 THEN ', se llevó la victoria' ELSE '' END
          + CASE WHEN a.P_SV >= 1 THEN ', se apuntó el salvado' ELSE '' END
        , 1, 2, '')                               AS detalle,
        ''                                        AS equipo_nombre,
        ''                                        AS rival_nombre,
        ''                                        AS oponente
FROM    dbo.retroDailyAS a
INNER JOIN dbo.dglMaster m ON m.retroID = a.PLAYER_ID
WHERE   a.B_HR >= 1 OR a.B_H >= 2 OR a.P_W >= 1 OR a.P_SV >= 1;

-- =====================================================================================
-- LA LISTA — «¿qué han hecho los dominicanos en el Juego de Estrellas?»
--
-- Trae TODAS las apariciones, no solo las 32 con actuación, porque la pregunta suele ser «¿y
-- cuántos han ido?». Son 283 de 111 jugadores.
-- =====================================================================================
/*
SELECT  m.nameList AS jugador, CAST(a.GAME_DT AS date) AS fecha, a.SEASON AS temporada,
        a.B_H AS hits, a.B_HR AS jonrones, a.B_RBI AS empujadas,
        a.P_OUT / 3.0 AS entradas, a.P_SO AS ponches, a.P_W AS gano, a.P_SV AS salvo
FROM    dbo.retroDailyAS a
INNER JOIN dbo.dglMaster m ON m.retroID = a.PLAYER_ID
ORDER BY a.GAME_DT, m.nameList;
*/
