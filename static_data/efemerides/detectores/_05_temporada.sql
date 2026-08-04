-- =====================================================================================
-- EL PRELUDIO DE TEMPORADA: el acumulado de cada jugador DENTRO de un año.
--
-- NO ES UN DETECTOR. Empieza por `_`.
--
-- PARA QUÉ. Los hitos de carrera (`_02_carrera.sql`) responden «¿qué día llegó a su jonrón 400 de por
-- vida?». Este responde otra pregunta distinta y igual de clásica: **«¿qué día llegó a 50 jonrones en
-- una temporada?»**. Son los números que la gente se sabe de memoria —los 60 de Sosa, los 300 ponches
-- de Pedro, las 20 victorias— y ninguno se puede sacar del acumulado de carrera.
--
-- SOLO TEMPORADA REGULAR, y esto es deliberado y va al revés que el resto del archivo. En todo lo
-- demás la postemporada entra (decisión del dueño). Acá NO puede entrar: «50 jonrones en una
-- temporada» es una cifra de temporada regular, la que sale en los récords y en la prensa. Sumarle
-- octubre daría un número que no coincide con ninguna fuente del mundo y que además movería la fecha
-- del cruce. Es la excepción, y existe porque el hito ES el número.
--
-- EL ORDEN DEL ACUMULADO es `fecha, game_id`. El `game_id` desempata los dobles juegos del mismo día:
-- sin él, el jonrón 50 podría atribuirse al primer juego cuando fue en el segundo.
-- =====================================================================================

IF OBJECT_ID('tempdb..#temporada') IS NOT NULL DROP TABLE #temporada;

SELECT  j.PLAYER_ID, j.mlb_id, j.nombre,
        j.game_id, j.fecha, j.temporada, j.game_type,
        j.equipo, j.rival, j.en_casa, j.equipo_nombre, j.rival_nombre,
        -- Lo de ESTE juego, que es lo que el texto necesita para decir «ese día bateó 2».
        j.B_HR, j.B_H, j.B_RBI, j.B_SB, j.P_SO, j.P_W, j.P_OUT, j.P_ER,
        -- Y el acumulado de la temporada HASTA este juego, incluido.
        SUM(j.B_HR)  OVER (PARTITION BY j.PLAYER_ID, j.temporada
                           ORDER BY j.fecha, j.game_id ROWS UNBOUNDED PRECEDING) AS hr_ac,
        SUM(j.B_H)   OVER (PARTITION BY j.PLAYER_ID, j.temporada
                           ORDER BY j.fecha, j.game_id ROWS UNBOUNDED PRECEDING) AS h_ac,
        SUM(j.B_RBI) OVER (PARTITION BY j.PLAYER_ID, j.temporada
                           ORDER BY j.fecha, j.game_id ROWS UNBOUNDED PRECEDING) AS rbi_ac,
        SUM(j.B_SB)  OVER (PARTITION BY j.PLAYER_ID, j.temporada
                           ORDER BY j.fecha, j.game_id ROWS UNBOUNDED PRECEDING) AS sb_ac,
        SUM(j.P_SO)  OVER (PARTITION BY j.PLAYER_ID, j.temporada
                           ORDER BY j.fecha, j.game_id ROWS UNBOUNDED PRECEDING) AS k_ac,
        SUM(j.P_W)   OVER (PARTITION BY j.PLAYER_ID, j.temporada
                           ORDER BY j.fecha, j.game_id ROWS UNBOUNDED PRECEDING) AS w_ac,
        -- EL TOTAL CON QUE CERRÓ LA TEMPORADA. Sin `ORDER BY`, la ventana es la temporada entera.
        -- Hace falta por dos razones: el texto puede decir «terminó con 66», y la MAGNITUD sale de
        -- acá y no del acumulado al cruzar —que siempre ronda el umbral y no distingue nada—. Así la
        -- temporada de 66 jonrones de Sosa pesa más que la de 50, que es lo correcto.
        SUM(j.B_HR)  OVER (PARTITION BY j.PLAYER_ID, j.temporada) AS hr_tot,
        SUM(j.B_H)   OVER (PARTITION BY j.PLAYER_ID, j.temporada) AS h_tot,
        SUM(j.B_RBI) OVER (PARTITION BY j.PLAYER_ID, j.temporada) AS rbi_tot,
        SUM(j.B_SB)  OVER (PARTITION BY j.PLAYER_ID, j.temporada) AS sb_tot,
        SUM(j.P_SO)  OVER (PARTITION BY j.PLAYER_ID, j.temporada) AS k_tot,
        SUM(j.P_W)   OVER (PARTITION BY j.PLAYER_ID, j.temporada) AS w_tot
INTO    #temporada
FROM    #juegos j
WHERE   j.game_type = 'R';

CREATE CLUSTERED INDEX ix_temporada ON #temporada(PLAYER_ID, temporada, fecha);
