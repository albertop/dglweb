-- =====================================================================================
-- El walk-off anticlimático: boleto o pelotazo con las bases llenas. Medido: 28 veces, 26
-- jugadores. Rareza 453.
--
-- SE LLAMABA `walkoff_bb` Y ERA UN NOMBRE FALSO. El detector siempre cubrió las TRES formas de
-- terminar un juego sin darle a la pelota —boleto, boleto intencional y pelotazo— y el texto las
-- distinguía bien fila por fila. Lo que mentía era el slug: decía «bb» y publicaba «lo golpearon».
-- Lo cazó el dueño leyendo la muestra el 2026-08-04. Ahora el nombre dice lo mismo que el titular.
--
-- Y las tres pertenecen juntas: lo que hace la efeméride no es qué lanzamiento fue, sino que el
-- juego se acabó SIN QUE EL BATEADOR LE PEGARA A NADA. Separarlas daría tres detectores de menos de
-- veinte filas cada uno contando la misma historia.
--
-- GRANO: turno al bate. Universo 822764. Sale de `#turnos` (preludio `_01_turnos.sql`).
--
-- Acá SÍ se nombra al lanzador: el turno se enfrentó a UN hombre, así que decirlo es verdad.
-- =====================================================================================
SELECT  'walkoff_sin_batear' AS tipo,
        'bateador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        822764 AS universo,
        'Walk-off sin batear la pelota contra {rival_nombre}: {detalle}.' AS plantilla,
        t.mlb_id, t.nombre, t.fecha, t.temporada, t.game_id, t.event_id, t.game_type,
        t.equipo, t.rival, t.en_casa,
        1 AS signo,
        t.wpa AS magnitud,
        t.wpa AS wpa_jugador,
        t.li AS li_max,
        CASE WHEN t.hbp = 1 THEN 'lo golpearon con las bases llenas' ELSE 'boleto con las bases llenas' END + ', ' + 'en el ' + t.inning_txt + CASE WHEN t.outs = 0 THEN ', sin outs' WHEN t.outs = 1 THEN ', con 1 out' ELSE ', con ' + CAST(t.outs AS varchar(1)) + ' outs' END AS detalle,
        t.equipo_nombre, t.rival_nombre, t.oponente
FROM    #turnos t
WHERE   t.es_walkoff = 1 AND (t.bb = 1 OR t.ibb = 1 OR t.hbp = 1);
