-- =====================================================================================
-- Grand slam. Medido: 520 veces, y 9 de ellos en postemporada. Rareza 325.
--
-- GRANO: turno al bate. Universo 822764. Sale de `#turnos` (preludio `_01_turnos.sql`).
--
-- Acá SÍ se nombra al lanzador: el turno se enfrentó a UN hombre, así que decirlo es verdad.
-- =====================================================================================
SELECT  'grand_slam' AS tipo,
        'bateador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        822764 AS universo,
        'Conectó un grand slam contra {rival_nombre}, ante {oponente}: {detalle}.' AS plantilla,
        t.mlb_id, t.nombre, t.fecha, t.temporada, t.game_id, t.event_id, t.game_type,
        t.equipo, t.rival, t.en_casa,
        1 AS signo,
        t.wpa AS magnitud,
        t.wpa AS wpa_jugador,
        t.li AS li_max,
        'en el ' + t.inning_txt + CASE WHEN t.outs = 0 THEN ', sin outs' WHEN t.outs = 1 THEN ', con 1 out' ELSE ', con ' + CAST(t.outs AS varchar(1)) + ' outs' END AS detalle,
        t.equipo_nombre, t.rival_nombre, t.oponente
FROM    #turnos t
WHERE   t.hr = 1 AND t.rbi = 4;
