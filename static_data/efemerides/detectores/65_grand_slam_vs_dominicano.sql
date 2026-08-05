-- =====================================================================================
-- GRAND SLAM DOMINICANO CONTRA LANZADOR DOMINICANO. Medido: 53 de los 520.
--
-- POR QUÉ SE REDUJO. El detector contaba TODOS los grand slams de dominicanos —520— y eso es casi
-- uno y medio por día del calendario: dejaba de ser noticia y empujaba fuera de la página a gestas
-- más raras del mismo día. Decisión del dueño el 2026-08-04: quedarse con los que fueron ANTE UN
-- LANZADOR DOMINICANO.
--
-- No es solo recortar por recortar; es un hecho distinto y mejor. Un grand slam más es un grand slam
-- más, pero un dominicano bateándoselo a otro dominicano es un duelo entre paisanos, y eso se cuenta
-- solo. Son 53 en 116 temporadas, 0,46 por temporada.
--
-- El efecto en el puntaje es el que corresponde: la rareza sube de 325 a ~425, o sea que pasa de
-- estar entre las corrientes a estar entre las buenas.
--
-- El primero fue Pedro Guerrero a Elías Sosa, el 28 de junio de 1983.
--
-- LO QUE SE PIERDE. Los otros 467 grand slams dejan de tener efeméride propia. Muchos sobreviven de
-- todos modos como parte de otra —los de walk-off entran por `62_walkoff_slam`, y los que cayeron en
-- juegos de varias empujadas entran por `21_rbi7`— pero un grand slam suelto ante un lanzador no
-- dominicano ya no genera fila. Es exactamente lo que se pidió.
--
-- GRANO: turno al bate. Universo 822764. Sale de `#turnos` (preludio `_01_turnos.sql`).
--
-- Acá SÍ se nombra al lanzador: el turno se enfrentó a UN hombre, así que decirlo es verdad. Y ahora
-- el nombre carga el doble de peso, porque es la mitad de la efeméride.
-- =====================================================================================
SELECT  'grand_slam_vs_dominicano' AS tipo,
        'un grand slam ante un lanzador dominicano' AS gesta,
        '' AS participantes,
        'bateador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        811955 AS universo,
        'Le conectó un grand slam a su compatriota {oponente}, de {rival_nombre}: {detalle}.' AS plantilla,
        t.mlb_id, t.nombre, t.fecha, t.temporada, t.game_id, t.event_id, t.game_type,
        t.equipo, t.rival, t.en_casa,
        1 AS signo,
        t.wpa AS magnitud,
        t.wpa AS wpa_jugador,
        t.li AS li_max,
        'en el ' + t.inning_txt + CASE WHEN t.outs = 0 THEN ', sin outs' WHEN t.outs = 1 THEN ', con 1 out' ELSE ', con ' + CAST(t.outs AS varchar(1)) + ' outs' END AS detalle,
        t.equipo_nombre, t.rival_nombre, t.oponente
FROM    #turnos t
WHERE   t.hr = 1 AND t.rbi = 4
  -- EL LANZADOR TAMBIÉN DOMINICANO. `#turnos` ya solo trae bateadores dominicanos; esto agrega la
  -- otra mitad del duelo. Se pregunta por `retroID` y no por el nombre, que no es único (3.0.1).
  AND EXISTS (SELECT 1 FROM dbo.dglMaster dm WHERE dm.retroID = t.lanzador_retro);

-- =====================================================================================
-- LA LISTA — «¿cuáles son esos 53 grand slams de dominicano a dominicano?»
-- =====================================================================================
/*
SELECT  CAST(g.GAME_DT AS date) AS fecha,
        b.nameList AS bateador, p.nameList AS lanzador,
        e.INN_CT AS inning, e.OUTS_CT AS outs
FROM    dbo.r24Events e
INNER JOIN dbo.dglMaster b ON b.retroID = e.BATTER_ID
INNER JOIN dbo.dglMaster p ON p.retroID = e.PITCHER_ID
LEFT  JOIN dbo.retroGamesReg g ON g.GAME_ID = e.GAME_ID
WHERE   e.HR = 1 AND e.RBI = 4
ORDER BY g.GAME_DT;
*/
