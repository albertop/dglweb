-- =====================================================================================
-- Walk-off de jonrón. Medido: 262 veces, 100 jugadores. Rareza 355.
--
-- GRANO: turno al bate. Universo 822764. Sale de `#turnos` (preludio `_01_turnos.sql`).
--
-- Acá SÍ se nombra al lanzador: el turno se enfrentó a UN hombre, así que decirlo es verdad.
-- =====================================================================================
SELECT  'walkoff_hr' AS tipo,
        'bateador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        822764 AS universo,
        'Walk-off de jonrón contra {rival_nombre}, ante {oponente}: {detalle}.' AS plantilla,
        t.mlb_id, t.nombre, t.fecha, t.temporada, t.game_id, t.event_id, t.game_type,
        t.equipo, t.rival, t.en_casa,
        1 AS signo,
        t.rbi AS magnitud,
        t.wpa AS wpa_jugador,
        t.li AS li_max,
        'en el ' + t.inning_txt + CASE WHEN t.outs = 0 THEN ', sin outs' WHEN t.outs = 1 THEN ', con 1 out' ELSE ', con ' + CAST(t.outs AS varchar(1)) + ' outs' END + CASE WHEN t.rbi = 1 THEN '' ELSE ', y empujó ' + CAST(t.rbi AS varchar(1)) END AS detalle,
        t.equipo_nombre, t.rival_nombre, t.oponente
FROM    #turnos t
WHERE   t.es_walkoff = 1 AND t.hr = 1;
