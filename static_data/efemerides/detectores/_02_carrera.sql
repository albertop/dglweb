-- =====================================================================================
-- EL PRELUDIO DE CARRERA: `#carrera`, los totales acumulados de cada dominicano juego a juego.
--
-- NO ES UN DETECTOR. Empieza por `_`, así que el motor lo corre antes y no le exige el contrato.
--
-- PARA QUÉ. «Un día como hoy, X llegó a su jonrón 300» es la efeméride clásica, y son 831 cruces —
-- el grupo más grande del archivo después de los cumpleaños. Los siete detectores de hito necesitan
-- exactamente lo mismo: el total del jugador ANTES y DESPUÉS de cada juego. Se calcula una vez.
--
-- SUMA TEMPORADA REGULAR Y POSTEMPORADA (decisión del dueño, 2026-08-03). No es como los cuenta MLB
-- —ellos separan— pero es coherente con el resto del archivo: si octubre cuenta para el ciclo, cuenta
-- para el hit 2000. Medido, la diferencia son 13 cruces: 818 solo con regular, 831 con las dos.
--
-- EL ORDEN ES `fecha, game_id` Y NO SOLO `fecha`. En un doble juego hay dos partidos el mismo día, y
-- sin el desempate la suma acumulada quedaría en un orden arbitrario — el hit 3000 podría salir
-- atribuido al primer juego cuando cayó en el segundo.
-- =====================================================================================

IF OBJECT_ID('tempdb..#carrera') IS NOT NULL DROP TABLE #carrera;

SELECT  j.PLAYER_ID, j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id, j.game_type,
        j.equipo, j.rival, j.en_casa, j.equipo_nombre, j.rival_nombre,
        j.wpa_bat, j.wpa_pit, j.li_max,
        -- Lo que hizo ESE día. El detector lo usa para el detalle del texto.
        j.B_H, j.B_HR, j.B_RBI, j.B_SB, j.P_SO, j.P_W, j.P_SV,
        j.P_OUT, j.P_H, j.P_ER,
        -- Y el acumulado HASTA ese juego, incluido.
        SUM(j.B_H)   OVER (PARTITION BY j.PLAYER_ID ORDER BY j.fecha, j.game_id ROWS UNBOUNDED PRECEDING) AS ac_h,
        SUM(j.B_HR)  OVER (PARTITION BY j.PLAYER_ID ORDER BY j.fecha, j.game_id ROWS UNBOUNDED PRECEDING) AS ac_hr,
        SUM(j.B_RBI) OVER (PARTITION BY j.PLAYER_ID ORDER BY j.fecha, j.game_id ROWS UNBOUNDED PRECEDING) AS ac_rbi,
        SUM(j.B_SB)  OVER (PARTITION BY j.PLAYER_ID ORDER BY j.fecha, j.game_id ROWS UNBOUNDED PRECEDING) AS ac_sb,
        SUM(j.P_SO)  OVER (PARTITION BY j.PLAYER_ID ORDER BY j.fecha, j.game_id ROWS UNBOUNDED PRECEDING) AS ac_k,
        SUM(j.P_W)   OVER (PARTITION BY j.PLAYER_ID ORDER BY j.fecha, j.game_id ROWS UNBOUNDED PRECEDING) AS ac_w,
        SUM(j.P_SV)  OVER (PARTITION BY j.PLAYER_ID ORDER BY j.fecha, j.game_id ROWS UNBOUNDED PRECEDING) AS ac_sv
INTO    #carrera
FROM    #juegos j;

CREATE CLUSTERED INDEX ix_carrera ON #carrera(PLAYER_ID, fecha, game_id);
