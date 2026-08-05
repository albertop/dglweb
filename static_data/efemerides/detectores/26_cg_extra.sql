-- =====================================================================================
-- JUEGO COMPLETO DE MÁS DE NUEVE ENTRADAS. Medido: 17 veces.
--
-- No es un juego completo cualquiera: es el que se fue a entradas extra y el mismo hombre siguió
-- lanzando. Hoy no existe — un abridor no pasa de las siete— así que el detector guarda una manera de
-- jugar que se acabó.
--
-- Y LA LISTA ES PRÁCTICAMENTE DE UN SOLO HOMBRE:
--
--     1963-07-02   Juan Marichal   16 entradas, 10 ponches, CERO carreras limpias
--     1966-05-26   Juan Marichal   14 entradas, 10 ponches, cero limpias
--     1969-08-19   Juan Marichal   13 entradas, 13 ponches
--     1968-06-27   Juan Marichal   11        1968-07-28   Juan Marichal   11
--
-- Las diez actuaciones más largas son TODAS de Marichal. Las 16 entradas de 1963 son el duelo contra
-- Warren Spahn en Candlestick Park, que Marichal ganó 1-0 — y el mismo juego que ya aparece como su
-- mejor actuación de por vida en valor de carreras. Dos caminos independientes llegando al mismo
-- juego es la mejor señal de que las dos definiciones están bien escritas.
--
-- SE DETECTA CON `P_OUT > 27` Y `P_CG >= 1`: más de veintisiete outs es más de nueve entradas. No se
-- usa el marcador ni el número de entradas del juego, porque lo que se cuenta es lo que LANZÓ ÉL.
--
-- OJO CON LOS 9⅓ Y 9⅔: entran, y deben entrar. Son juegos que se fueron a extra y terminaron a mitad
-- de entrada con él todavía en la lomita.
--
-- CONVIVE CON `37_cg90` Y `34_cg_dominante` sin problema: son juegos completos vistos por ejes
-- distintos —economía, dominio, resistencia— y la fusión se queda con el más raro cuando coinciden.
--
-- GRANO: juego-jugador (292.948).
-- =====================================================================================
SELECT  'cg_extra' AS tipo,
        'un juego completo de más de nueve entradas' AS gesta,
        '' AS participantes,
        'lanzador'                                AS rol,
        'completa'                                AS cobertura,
        288826                                    AS universo,
        1                                         AS situar,
        'Lanzó el juego completo y se fue a entradas extra contra {rival_nombre}: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                         AS signo,
        -- Los outs, no las entradas: distingue al de 9⅔ del de 9⅓, y al de 16 de todos los demás.
        j.P_OUT                                   AS magnitud,
        NULL                                      AS wpa_jugador,
        j.li_max,
        CAST(j.P_OUT / 3 AS varchar(2)) + ' entradas'
            + CASE WHEN j.P_OUT % 3 = 1 THEN ' y un tercio' WHEN j.P_OUT % 3 = 2 THEN ' y dos tercios' ELSE '' END
            + ', ' + CAST(j.P_SO AS varchar(2)) + CASE WHEN j.P_SO = 1 THEN ' ponche' ELSE ' ponches' END
            + CASE WHEN j.P_ER = 0 THEN ' y ni una carrera limpia'
                   WHEN j.P_ER = 1 THEN ' y 1 carrera limpia'
                   ELSE ' y ' + CAST(j.P_ER AS varchar(2)) + ' limpias' END AS detalle,
        j.equipo_nombre, j.rival_nombre,
        ''                                        AS oponente
FROM    #juegos j
WHERE   j.P_CG >= 1
  AND   j.P_OUT > 27;

-- =====================================================================================
-- LA LISTA — «¿quiénes lanzaron juego completo de más de nueve entradas?»
-- =====================================================================================
/*
SELECT  m.nameList AS lanzador, CAST(r.GAME_DT AS date) AS fecha,
        r.P_OUT / 3.0 AS entradas, r.P_SO AS ponches, r.P_ER AS limpias, r.P_H AS hits
FROM    dbo.retroDailyReg r
INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
WHERE   r.P_CG >= 1 AND r.P_OUT > 27
ORDER BY r.P_OUT DESC, fecha;
*/
