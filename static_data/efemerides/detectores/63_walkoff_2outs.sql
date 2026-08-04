-- =====================================================================================
-- El batazo más dramático que hay: dos outs, perdiendo, y se acabó el juego. Medido: 22 veces,
-- 17 jugadores. Rareza 464.
--
-- LA MAGNITUD ES POR CUÁNTO IBA PERDIENDO. Remontar de tres es más que remontar de una, y el WPA
-- solo no lo separa bien porque satura cerca de 1.
--
-- GRANO: turno al bate. Universo 822764. Sale de `#turnos` (preludio `_01_turnos.sql`).
--
-- Acá SÍ se nombra al lanzador: el turno se enfrentó a UN hombre, así que decirlo es verdad.
-- =====================================================================================
SELECT  'walkoff_2outs' AS tipo,
        'bateador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        822764 AS universo,
        'Terminó el juego con un jonrón con dos outs y perdiendo, contra {rival_nombre} ante {oponente}: {detalle}.' AS plantilla,
        t.mlb_id, t.nombre, t.fecha, t.temporada, t.game_id, t.event_id, t.game_type,
        t.equipo, t.rival, t.en_casa,
        1 AS signo,
        (t.sc_riv - t.sc_bat) AS magnitud,
        t.wpa AS wpa_jugador,
        t.li AS li_max,
        'iban ' + CAST(t.sc_bat AS varchar(2)) + '-' + CAST(t.sc_riv AS varchar(2)) + ' abajo en el ' + t.inning_txt AS detalle,
        t.equipo_nombre, t.rival_nombre, t.oponente
FROM    #turnos t
WHERE   t.es_walkoff = 1 AND t.hr = 1 AND t.outs = 2 AND t.sc_bat < t.sc_riv;
