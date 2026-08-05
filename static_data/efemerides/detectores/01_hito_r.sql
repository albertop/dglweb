-- =====================================================================================
-- LA CARRERA ANOTADA 1.500 Y LA 2.000. Medido: 4 dominicanos llegan a 1.500 y UNO a 2.000.
--
--     Alex Rodriguez   2.064   <- el unico que ha pasado de 2.000
--     Albert Pujols    1.971
--     Manny Ramirez    1.611
--     Sammy Sosa       1.483 … no llega
--
-- LAS DOS MARCAS SON LAS QUE PIDIO EL DUENO, y estan bien puestas: mil quinientas carreras anotadas
-- son cuatro dominicanos en 116 temporadas y dos mil es uno solo. Con 1.000 serian una docena y la
-- efemeride se diluiria.
--
-- POR QUE NO EXISTIA: el archivo tenia hitos de hits, jonrones, empujadas, robos, ponches, victorias
-- y salvados — pero no de carreras anotadas, que es la mitad de la ofensiva que no depende de quien
-- venga detras a empujarte.
--
-- LA LISTA DE MARCAS ES EXPLICITA, no un escalon fijo. Ver 81_hito_hr.sql para el porque: una
-- progresion regular no puede expresar «450 pero no 400», y estas cifras se eligen por lo que
-- significan en su propia estadistica.
--
-- Sale de #carrera (preludio _02_carrera.sql), que trae el acumulado juego a juego. EL CRUCE se
-- detecta comparando el acumulado de este juego contra el de antes.
--
-- situar = 2: la frase «uno de los N dominicanos» solo aparece si es el primero o el unico, igual
-- que en los demas hitos de carrera. Ver docs/EFEMERIDES.md 3.5.
--
-- SUMA TEMPORADA REGULAR Y POSTEMPORADA, como todos los hitos de carrera y al reves que los de
-- temporada (5.6.1).
--
-- GRANO: juego-jugador (292.948).
-- =====================================================================================
WITH marcas AS (
    SELECT marca FROM (VALUES (1500), (2000)) v(marca)
)
SELECT  'hito_r' AS tipo,
        'un hito de carreras anotadas de por vida' AS gesta,
        '' AS participantes,
        'bateador' AS rol,
        'completa' AS cobertura,
        2 AS situar,
        288826 AS universo,
        -- La plantilla se declara por fila, asi que puede traer la frase que el motor no sabe
        -- calcular: cuantos dominicanos han llegado A ESA CIFRA. Solo se dice cuando son cinco o
        -- menos — con veinte no es noticia, es una lista. Ver docs/EFEMERIDES.md 4.7.
        --
        -- Y si ese dia solo hizo uno, la coletilla no se pone: «llego a 500 dobles: ese dia bateo 1
        -- doble» dice dos veces la misma cosa.
        CASE WHEN c.B_R <= 1
             THEN 'Llegó a {magnitud} carreras anotadas de por vida, contra {rival_nombre}.'
             ELSE 'Llegó a {magnitud} carreras anotadas de por vida, contra {rival_nombre}: {detalle}.' END
            + CASE WHEN cu.cuantos <= 5
                   THEN CASE WHEN cu.cuantos = 1 THEN ' Es el único dominicano que ha llegado ahí.'
                             ELSE ' Solo ' + CAST(cu.cuantos AS varchar(2)) + ' dominicanos han llegado ahí.' END
                   ELSE '' END AS plantilla,
        c.mlb_id, c.nombre, c.fecha, c.temporada, c.game_id,
        0 AS event_id,
        c.game_type, c.equipo, c.rival, c.en_casa,
        1 AS signo,
        mk.marca AS magnitud,
        c.wpa_bat AS wpa_jugador,
        c.li_max,
        'ese día anotó ' + CAST(c.B_R AS varchar(2))
            + CASE WHEN c.B_R = 1 THEN ' carrera' ELSE ' carreras' END AS detalle,
        c.equipo_nombre, c.rival_nombre,
        '' AS oponente
FROM    #carrera c
INNER JOIN marcas mk ON c.ac_r >= mk.marca AND (c.ac_r - c.B_R) < mk.marca
-- Cuantos dominicanos DISTINTOS alcanzaron alguna vez esta cifra. Por PLAYER_ID, nunca por nombre.
CROSS APPLY (SELECT COUNT(DISTINCT x.PLAYER_ID) AS cuantos
             FROM   #carrera x
             WHERE  x.ac_r >= mk.marca) cu
WHERE   c.B_R > 0;

-- =====================================================================================
-- LA LISTA — quienes han llegado
-- =====================================================================================
/*
WITH d AS (
    SELECT r.PLAYER_ID, r.B_R AS v FROM dbo.retroDailyReg r
    INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
    UNION ALL
    SELECT p.PLAYER_ID, p.B_R FROM dbo.retroDailyPost p
    INNER JOIN dbo.dglMaster m ON m.retroID = p.PLAYER_ID
)
SELECT  m.nameList AS jugador, SUM(d.v) AS total
FROM    d INNER JOIN dbo.dglMaster m ON m.retroID = d.PLAYER_ID
GROUP BY m.nameList
ORDER BY total DESC;
*/
