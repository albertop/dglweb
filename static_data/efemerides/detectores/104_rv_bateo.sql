-- =====================================================================================
-- EL MEJOR JUEGO OFENSIVO, MEDIDO EN CARRERAS DE VALOR. Medido: 91 juegos, 43 jugadores.
--
-- Idea del dueño, y es distinta de todo lo demás del inventario: en vez de preguntar «¿cuántos
-- jonrones?» o «¿cuántos hits?», suma el `RUN_VALUE` de TODOS los turnos del jugador en ese juego.
-- Da una sola medida de cuánto produjo, sin importar cómo lo hizo.
--
-- Estaba diseñado desde el principio y nunca se había construido — figuraba en la 5.12. Lo reclamó
-- el dueño el 2026-08-04.
--
-- EL UMBRAL, sobre los 288.826 juegos-jugador:
--
--     4,0 carreras   454 juegos, 122 jugadores   3,9 por temporada   <- rutina
--     4,5            206, 77                     1,8
--     5,0             91, 43                     0,8                 <- el corte
--     5,5             39, 25                     0,3
--     6,0             11, 11                     0,1
--
-- LO QUE LO VALIDA ES QUE ENCUENTRA SOLO LO QUE YA SABÍAMOS. El mejor juego ofensivo dominicano por
-- esta métrica es el mismo que sale por el camino de las empujadas: **Alex Rodríguez, 26 de abril de
-- 2005**, con 3 jonrones y 10 empujadas. Dos métodos independientes llegando al mismo juego es la
-- mejor señal de que las dos definiciones están bien escritas.
--
-- POR QUÉ `RUN_VALUE` Y NO `WPA`. Miden cosas distintas y las dos están en `r24Events`: el valor de
-- carreras dice cuánto PRODUJO, el WPA cuánto ACERCÓ LA VICTORIA. Un juegazo en una derrota de 12-2
-- tiene valor alto y WPA bajo. Acá se usa `RUN_VALUE` para el umbral —es la gesta— y el WPA sigue
-- alimentando el bono de impacto (4.3), que es donde el contexto debe pesar.
--
-- SE VA A SOLAPAR MUCHO, y está bien: un juego de 5 carreras de valor casi siempre es también un
-- juego de 3 jonrones o de 7 empujadas. La fusión (sección 7) se queda con el más raro y este pasa a
-- etiqueta. Lo que aporta son los juegos que NINGÚN umbral de conteo encuentra: cuatro dobles y dos
-- boletos en los momentos justos no dispara ningún otro detector.
--
-- COBERTURA COMPLETA: `RUN_VALUE` cubre 1910-2025 en los 16,1 millones de eventos.
--
-- GRANO: juego-jugador (288.826).
-- =====================================================================================
WITH rv AS (
    SELECT  e.GAME_ID, e.BATTER_ID, SUM(e.RUN_VALUE) AS carreras
    FROM    dbo.r24Events e
    WHERE   e.BAT_EVENT_FL = 1
      AND   e.GAME_TYPE = 'R'          -- solo temporada regular, ver `_00_comun.sql`
    GROUP BY e.GAME_ID, e.BATTER_ID
    HAVING  SUM(e.RUN_VALUE) >= 5.0
)
SELECT  'rv_bateo' AS tipo,
        'un juego de 5+ carreras de valor generadas' AS gesta,
        'bateador'                                AS rol,
        'completa'                                AS cobertura,
        288826                                    AS universo,
        1                                         AS situar,
        'Produjo {detalle} contra {rival_nombre}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                         AS signo,
        rv.carreras                               AS magnitud,
        j.wpa_bat                                 AS wpa_jugador,
        j.li_max,
        -- El número con UN decimal y con PUNTO, como el resto del archivo (dueño).
        CAST(CAST(rv.carreras AS decimal(4,1)) AS varchar(6)) + ' carreras de valor: '
            + CAST(j.B_H AS varchar(2)) + CASE WHEN j.B_H = 1 THEN ' hit' ELSE ' hits' END
            + CASE WHEN j.B_HR > 0
                   THEN ', ' + CAST(j.B_HR AS varchar(2))
                        + CASE WHEN j.B_HR = 1 THEN ' jonrón' ELSE ' jonrones' END
                   ELSE '' END
            + CASE WHEN j.B_RBI > 0
                   THEN ' y ' + CAST(j.B_RBI AS varchar(2))
                        + CASE WHEN j.B_RBI = 1 THEN ' empujada' ELSE ' empujadas' END
                   ELSE '' END                    AS detalle,
        j.equipo_nombre, j.rival_nombre,
        ''                                        AS oponente
FROM    rv
INNER JOIN #juegos j ON j.game_id = rv.GAME_ID AND j.PLAYER_ID = rv.BATTER_ID;

-- =====================================================================================
-- LA LISTA — «¿cuáles son los mejores juegos ofensivos dominicanos?»
-- =====================================================================================
/*
SELECT  TOP 30 m.nameList AS jugador, CAST(g.GAME_DT AS date) AS fecha,
        CAST(SUM(e.RUN_VALUE) AS decimal(5,2)) AS carreras_de_valor
FROM    dbo.r24Events e
INNER JOIN dbo.dglMaster m ON m.retroID = e.BATTER_ID
LEFT  JOIN dbo.retroGamesReg g ON g.GAME_ID = e.GAME_ID
WHERE   e.BAT_EVENT_FL = 1 AND e.GAME_TYPE = 'R'
GROUP BY m.nameList, CAST(g.GAME_DT AS date)
ORDER BY carreras_de_valor DESC;
*/
