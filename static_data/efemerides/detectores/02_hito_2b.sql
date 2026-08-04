-- =====================================================================================
-- EL DOBLE 450, 500 Y 600. Medido: 10 dominicanos llegan a 450, 6 a 500 y 3 a 600.
--
--     Albert Pujols    704       Robinson Cano    582
--     David Ortiz      654       Manny Ramirez    566
--     Adrian Beltre    642       Alex Rodriguez   564
--
-- LAS TRES MARCAS LAS PIDIO EL DUENO, y no estan igualmente espaciadas a proposito: 450 abre la
-- puerta a diez nombres, 500 la cierra a seis y 600 a tres. Es la progresion que tiene sentido en
-- ESTA estadistica, no la que saldria de dividir por cien.
--
-- El doble es el batazo del bateador completo — ni el poder puro del jonron ni el contacto puro del
-- sencillo— y hasta ahora el archivo no lo celebraba en ninguna parte de la carrera.
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
    SELECT marca FROM (VALUES (450), (500), (600)) v(marca)
)
SELECT  'hito_2b' AS tipo,
        'un hito de dobles de por vida' AS gesta,
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
        CASE WHEN c.B_2B <= 1
             THEN 'Llegó a {magnitud} dobles de por vida, contra {rival_nombre}.'
             ELSE 'Llegó a {magnitud} dobles de por vida, contra {rival_nombre}: {detalle}.' END
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
        'ese día bateó ' + CAST(c.B_2B AS varchar(2))
            + CASE WHEN c.B_2B = 1 THEN ' doble' ELSE ' dobles' END AS detalle,
        c.equipo_nombre, c.rival_nombre,
        '' AS oponente
FROM    #carrera c
INNER JOIN marcas mk ON c.ac_2b >= mk.marca AND (c.ac_2b - c.B_2B) < mk.marca
-- Cuantos dominicanos DISTINTOS alcanzaron alguna vez esta cifra. Por PLAYER_ID, nunca por nombre.
CROSS APPLY (SELECT COUNT(DISTINCT x.PLAYER_ID) AS cuantos
             FROM   #carrera x
             WHERE  x.ac_2b >= mk.marca) cu
WHERE   c.B_2B > 0;

-- =====================================================================================
-- LA LISTA — quienes han llegado
-- =====================================================================================
/*
WITH d AS (
    SELECT r.PLAYER_ID, r.B_2B AS v FROM dbo.retroDailyReg r
    INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
    UNION ALL
    SELECT p.PLAYER_ID, p.B_2B FROM dbo.retroDailyPost p
    INNER JOIN dbo.dglMaster m ON m.retroID = p.PLAYER_ID
)
SELECT  m.nameList AS jugador, SUM(d.v) AS total
FROM    d INNER JOIN dbo.dglMaster m ON m.retroID = d.PLAYER_ID
GROUP BY m.nameList
ORDER BY total DESC;
*/