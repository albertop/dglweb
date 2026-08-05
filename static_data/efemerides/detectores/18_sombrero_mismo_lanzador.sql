-- =====================================================================================
-- EL SOMBRERO DORADO DE UN SOLO HOMBRE: los cuatro ponches, del MISMO lanzador.
--
-- ES EL ÚNICO SOMBRERO DORADO QUE PUBLICA EL ARCHIVO. El detector pasó por tres versiones y las dos
-- primeras se retiraron por anchas (dueño). Medido:
--
--     4 ponches en el juego, de quien sea        499 juegos   <- primera version, retirada
--     4 ponches en 4 apariciones exactas         231          <- segunda version, retirada
--     4 ponches DEL MISMO LANZADOR                29 juegos, 25 bateadores   <- este
--
-- POR QUÉ SE QUEDÓ ESTE Y NO OTRO. Poncharse cuatro veces contra cuatro lanzadores distintos es una
-- mala tarde repartida, y con 231 filas seguía siendo el detector más abundante del inventario.
-- Poncharse cuatro veces contra EL MISMO es que un hombre te tuvo el número toda la noche, y ahí sí
-- hay historia: no es que el bateador estuviera mal, es que el otro pudo con él cada vez que se
-- vieron. Veintinueve en 116 temporadas.
--
-- EL ESCALÓN DE ARRIBA SIGUE EN PIE: `51_sombrero_platino` son 5 ponches en un juego, sin pedir que
-- sean del mismo lanzador — a esa altura el número ya basta. Y `52_sombrero_titanio` (6+) espera
-- vacío al primero que lo haga.
--
-- ESTE DETECTOR NECESITA `r24Events`, no el game log: `retroDaily` dice cuántos ponches hubo pero no
-- quién los propinó. Hay que agrupar los eventos por (juego, bateador, lanzador).
--
-- LA CONTRAPARTE, vista desde el montículo, es `19_sombrero_propinado`.
--
-- `signo = -1`: media escala en todo, techo 400. Ver docs/EFEMERIDES.md 4.5.
--
-- GRANO: juego-jugador (292.948).
-- =====================================================================================
WITH duelo AS (
    SELECT  e.GAME_ID, e.BATTER_ID, e.PITCHER_ID, COUNT(1) AS ponches
    FROM    dbo.r24Events e
    WHERE   e.SO = 1 AND e.GAME_TYPE = 'R'  -- solo temporada regular, ver `_00_comun.sql`
    GROUP BY e.GAME_ID, e.BATTER_ID, e.PITCHER_ID
    HAVING  COUNT(1) >= 4
)
SELECT  'sombrero_mismo_lanzador' AS tipo,
        '4 ponches del mismo lanzador en un juego' AS gesta,
        '' AS participantes,
        'bateador'                                AS rol,
        'completa'                                AS cobertura,
        288826                                    AS universo,
        1                                         AS situar,
        'Se puso el sombrero dorado contra {rival_nombre} y se lo puso un solo hombre: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        -1                                        AS signo,
        d.ponches                                 AS magnitud,
        NULL                                      AS wpa_jugador,
        j.li_max,
        COALESCE(lz.nombre, 'el mismo lanzador') + ' lo ponchó ' + CAST(d.ponches AS varchar(2)) + ' veces' AS detalle,
        j.equipo_nombre, j.rival_nombre,
        COALESCE(lz.nombre, '')                   AS oponente
FROM    duelo d
INNER JOIN #juegos j ON j.game_id = d.GAME_ID AND j.PLAYER_ID = d.BATTER_ID
LEFT  JOIN #nombres lz ON lz.retro_id = d.PITCHER_ID
-- =====================================================================================
-- SI EL LANZADOR TAMBIÉN ES DOMINICANO, ESTA FILA NO SE PUBLICA.
-- =====================================================================================
--
-- Lo cazó el dueño: el mismo duelo saldría DOS VECES EL MISMO DÍA, una contando el sombrero del
-- bateador y otra el del lanzador, y la fusión no puede unirlas porque son dos jugadores distintos
-- —clave distinta— aunque el hecho sea uno solo.
--
-- Se calla este lado y habla `19_sombrero_propinado`, por dos razones: es la versión POSITIVA del
-- mismo hecho, y además nombra a los dos hombres, así que no se pierde nada.
--
-- Medido: pasa UNA sola vez en 116 temporadas — **Pedro Martínez ponchando cuatro veces a Alfonso
-- Soriano el 16 de octubre de 2003**, séptimo juego de la serie de campeonato. Una fila, pero es la
-- clase de fila que se nota.
WHERE   NOT EXISTS (SELECT 1 FROM dbo.dglMaster dm WHERE dm.retroID = d.PITCHER_ID);

-- =====================================================================================
-- LA LISTA — «¿a quiénes los ponchó cuatro veces el mismo lanzador?»
-- =====================================================================================
/*
WITH duelo AS (
    SELECT e.GAME_ID, e.BATTER_ID, e.PITCHER_ID, COUNT(1) AS ponches
    FROM   dbo.r24Events e WHERE e.SO = 1
    GROUP BY e.GAME_ID, e.BATTER_ID, e.PITCHER_ID HAVING COUNT(1) >= 4
),
f AS (SELECT GAME_ID, CAST(GAME_DT AS date) AS fecha FROM dbo.retroGamesReg
      UNION ALL SELECT GAME_ID, CAST(GAME_DT AS date) FROM dbo.retroGamesPost)
SELECT  f.fecha, m.nameList AS bateador, d.ponches, d.PITCHER_ID AS lanzador
FROM    duelo d
INNER JOIN dbo.dglMaster m ON m.retroID = d.BATTER_ID
LEFT  JOIN f ON f.GAME_ID = d.GAME_ID
ORDER BY f.fecha;
*/
