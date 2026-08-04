-- =====================================================================================
-- EL PRELUDIO DE STATCAST: `#sc_inning`, cada media entrada lanzada por un dominicano desde 2008,
-- con su conteo de lanzamientos.
--
-- NO ES UN DETECTOR. Empieza por `_`.
--
-- POR QUÉ ESTE PRELUDIO ES DISTINTO A LOS OTROS TRES: SU COBERTURA ES PARCIAL.
--
-- `scastPitch` empieza en 2008, no en 1910. Todo lo que salga de acá ve 19 temporadas de 116, así
-- que los detectores que lo usen declaran `cobertura = 'parcial'` y el motor les apaga los totales:
-- «uno de los N dominicanos» sería mentira cuando solo se ve una sexta parte de la historia. Regla
-- del dueño. Ver docs/EFEMERIDES.md 5.2.5.
--
-- EL PUENTE CON RETROSHEET ES POR JUGADOR Y FECHA, y esa decisión tiene su porqué.
--
-- `scastPitch` identifica equipos con las abreviaturas de MLB y Retrosheet con las suyas, y NO
-- coinciden: de 31 códigos de Statcast, 12 no existen en Retrosheet — AZ/ARI, NYY/NYA, LAD/LAN,
-- CHC/CHN, CWS/CHA, KC/KCA, NYM/NYN, SD/SDN, SF/SFN, STL/SLN, TB/TBA, WSH/WAS.
--
-- Escribir esa tabla de equivalencias a mano habría sido meter datos de memoria, que es justo lo que
-- este proyecto no se permite. En vez de eso se une por `(mlb_id, fecha)` contra `#juegos`, que ya
-- trae los nombres de equipo resueltos por época. Comprobado sobre los innings inmaculados: los 8
-- casan con UN solo juego, cero ambiguos y cero sin casar.
--
-- Y HAY UN EFECTO DEL PUENTE QUE NO ES UN FALLO: STATCAST VA POR DELANTE DE RETROSHEET.
--
-- Statcast publica en vivo y ya tiene 2026; la última temporada de Retrosheet es 2025. Así que un
-- hecho de la temporada en curso NO tiene juego contra el cual resolver equipo y rival, y el `INNER
-- JOIN` con `#puente` lo deja fuera.
--
-- Se ve en los datos: de los 11 innings de tres lanzamientos, entran 10. El que falta es el de Blas
-- Castaño del 2026-05-24, y no falta por error sino porque Retrosheet todavía no ha publicado esa
-- temporada.
--
-- ESTO ENCAJA CON LA CADENCIA DEL PROYECTO Y NO HAY QUE ARREGLARLO: el exportador corre una vez al
-- año DESPUÉS de que Retrosheet publica (sección 1 del diseño), y para entonces esos hechos entran
-- solos. Si alguien corre esto a mitad de temporada y echa en falta algo reciente, la explicación es
-- esta y no un fallo del puente.
-- =====================================================================================

IF OBJECT_ID('tempdb..#sc_inning') IS NOT NULL DROP TABLE #sc_inning;

SELECT  s.pitcher                          AS mlb_id,
        CAST(s.game_date AS date)          AS fecha,
        s.game_pk,
        s.inning,
        s.inning_topbot,
        COUNT(1)                           AS lanzamientos,
        SUM(CASE WHEN s.events IN ('strikeout','strikeout_double_play') THEN 1 ELSE 0 END) AS ponches,
        -- Un turno «terminado» es aquel donde `events` trae algo: el lanzamiento que resolvió el
        -- turno. Contarlos da los outs de la entrada sin tener que interpretar cada jugada.
        SUM(CASE WHEN s.events IS NOT NULL AND s.events <> '' THEN 1 ELSE 0 END) AS turnos
INTO    #sc_inning
FROM    dbo.scastPitch s
INNER JOIN dbo.dglMaster m ON m.mlbID = s.pitcher
GROUP BY s.pitcher, CAST(s.game_date AS date), s.game_pk, s.inning, s.inning_topbot;

CREATE CLUSTERED INDEX ix_sc_inning ON #sc_inning(mlb_id, fecha);

-- --- El puente hacia el contexto de Retrosheet -----------------------------------------
-- Una fila por (jugador, fecha) con el juego resuelto. El `MIN(game_id)` es el desempate para los
-- dobles juegos: hoy no hay ninguno entre las gestas de Statcast —comprobado— pero si mañana lo hay,
-- es mejor elegir uno de forma estable que devolver la fila dos veces.
IF OBJECT_ID('tempdb..#puente') IS NOT NULL DROP TABLE #puente;

SELECT  j.mlb_id,
        j.fecha,
        MIN(j.game_id)          AS game_id,
        MIN(j.temporada)        AS temporada,
        MIN(j.game_type)        AS game_type,
        MIN(j.equipo)           AS equipo,
        MIN(j.rival)            AS rival,
        MIN(j.en_casa)          AS en_casa,
        MIN(j.equipo_nombre)    AS equipo_nombre,
        MIN(j.rival_nombre)     AS rival_nombre
INTO    #puente
FROM    #juegos j
GROUP BY j.mlb_id, j.fecha;

CREATE UNIQUE CLUSTERED INDEX ix_puente ON #puente(mlb_id, fecha);
