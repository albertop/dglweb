-- =====================================================================================
-- El walk-off de GRAND SLAM. Medido: 20 veces, 17 jugadores. Rareza 468.
--
-- OJO: este detector estuvo mal definido en el diseño. Se escribió como «walk-off con 2 outs y bases
-- llenas» (69 casos), que NO es un grand slam — son bases llenas, pero el batazo pudo ser cualquier
-- cosa. El de verdad son 20. Lo señaló el dueño al cruzar la lista de MLB.
--
-- GRANO: turno al bate. Universo 822764. Sale de `#turnos` (preludio `_01_turnos.sql`).
--
-- Acá SÍ se nombra al lanzador: el turno se enfrentó a UN hombre, así que decirlo es verdad.
-- =====================================================================================
SELECT  'walkoff_slam' AS tipo,
        'un walk-off de grand slam' AS gesta,
        'bateador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        811955 AS universo,
        'Walk-off de grand slam contra {rival_nombre}, ante {oponente}: {detalle}.' AS plantilla,
        t.mlb_id, t.nombre, t.fecha, t.temporada, t.game_id, t.event_id, t.game_type,
        t.equipo, t.rival, t.en_casa,
        1 AS signo,
        t.wpa AS magnitud,
        t.wpa AS wpa_jugador,
        t.li AS li_max,
        'en el ' + t.inning_txt + CASE WHEN t.outs = 0 THEN ', sin outs' WHEN t.outs = 1 THEN ', con 1 out' ELSE ', con ' + CAST(t.outs AS varchar(1)) + ' outs' END AS detalle,
        t.equipo_nombre, t.rival_nombre, t.oponente
FROM    #turnos t
WHERE   t.es_walkoff = 1 AND t.hr = 1 AND t.rbi = 4;
