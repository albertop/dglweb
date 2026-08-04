-- =====================================================================================
-- EL PRELUDIO DE ALINEACIONES: quiénes estaban en el terreno en cada media entrada.
--
-- NO ES UN DETECTOR. Empieza por `_`.
--
-- PARA QUÉ. Dos efemérides que no son de un jugador sino de una FOTO: el jardín entero dominicano y
-- el cuadro entero dominicano. Medido: 131 juegos con jardín, 12 con cuadro, y NINGUNO con los dos a
-- la vez en 116 temporadas.
--
-- `retroEventsReg` trae en cada evento quién ocupaba cada posición —`POS3_FLD_ID` a `POS9_FLD_ID`—
-- así que la alineación defensiva se lee directa. Se agrupa por media entrada porque es la unidad
-- en que la formación se mantiene: dentro de una media entrada nadie cambia de puesto.
--
-- LA POSTEMPORADA ENTRA, como en todo el archivo. Son 146.482 eventos contra 16 millones, así que
-- cuesta poco y no dejarla fuera evita una asimetría difícil de explicar después.
-- =====================================================================================

IF OBJECT_ID('tempdb..#defensa') IS NOT NULL DROP TABLE #defensa;

SELECT  x.GAME_ID AS game_id, x.INN_CT AS inning, x.BAT_HOME_ID AS batea_casa,
        MIN(x.PIT_ID) AS p1, MIN(x.POS2_FLD_ID) AS p2,
        MIN(x.POS3_FLD_ID) AS p3, MIN(x.POS4_FLD_ID) AS p4,
        MIN(x.POS5_FLD_ID) AS p5, MIN(x.POS6_FLD_ID) AS p6,
        MIN(x.POS7_FLD_ID) AS p7, MIN(x.POS8_FLD_ID) AS p8, MIN(x.POS9_FLD_ID) AS p9
INTO    #defensa
FROM (
    SELECT e.GAME_ID, e.INN_CT, e.BAT_HOME_ID, e.PIT_ID, e.POS2_FLD_ID,
           e.POS3_FLD_ID, e.POS4_FLD_ID, e.POS5_FLD_ID, e.POS6_FLD_ID,
           e.POS7_FLD_ID, e.POS8_FLD_ID, e.POS9_FLD_ID
    FROM   dbo.retroEventsReg e
    UNION ALL
    SELECT p.GAME_ID, p.INN_CT, p.BAT_HOME_ID, p.PIT_ID, p.POS2_FLD_ID,
           p.POS3_FLD_ID, p.POS4_FLD_ID, p.POS5_FLD_ID, p.POS6_FLD_ID,
           p.POS7_FLD_ID, p.POS8_FLD_ID, p.POS9_FLD_ID
    FROM   dbo.retroEventsPost p
) x
GROUP BY x.GAME_ID, x.INN_CT, x.BAT_HOME_ID;

CREATE CLUSTERED INDEX ix_defensa ON #defensa(game_id);

-- --- Cuántos juegos lleva cada dominicano en su carrera -------------------------------
-- Sirve para ELEGIR A QUIÉN SE LE ATRIBUYE la efeméride, y es una decisión que conviene explicar.
--
-- El contrato tiene UN `mlb_id` por fila, pero estas gestas son de tres o cuatro hombres a la vez.
-- Emitir una fila por cada uno daría tres efemérides idénticas el mismo día; emitir una sola obliga
-- a elegir. Se elige al de MÁS JUEGOS DE CARRERA —el más reconocible— y el texto nombra a todos.
--
-- Así el sitio tiene a quién enlazar y el lector se entera de los tres. La alternativa sería un
-- `rol = equipo` sin `mlb_id`, y eso es justo lo que el dueño descartó para las gestas de equipo.
IF OBJECT_ID('tempdb..#huella') IS NOT NULL DROP TABLE #huella;
SELECT  j.PLAYER_ID AS retro_id, MIN(j.mlb_id) AS mlb_id, MIN(j.nombre) AS nombre, COUNT(1) AS juegos
INTO    #huella
FROM    #juegos j
GROUP BY j.PLAYER_ID;

CREATE UNIQUE CLUSTERED INDEX ix_huella ON #huella(retro_id);
