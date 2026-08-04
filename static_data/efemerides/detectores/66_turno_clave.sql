-- =====================================================================================
-- El turno que decidió un juego: mucha tensión Y mucho desenlace. Medido: 154 veces. Rareza 342.
--
-- EL CORTE PIDE LAS DOS COSAS, y por eso son 154 y no miles. Solo `LI >= 3` daría 5.159 turnos
-- tensos que NO decidieron nada, y tensión sin desenlace no es efeméride. Ver docs/EFEMERIDES.md 5.3.
--
-- La escala de `LI` está verificada: media 0,940 sobre 4,7 M de turnos, máximo 7,17. Un 2 es el
-- doble de tensión que un turno cualquiera.
--
-- GRANO: turno al bate. Universo 822764. Sale de `#turnos` (preludio `_01_turnos.sql`).
--
-- Acá SÍ se nombra al lanzador: el turno se enfrentó a UN hombre, así que decirlo es verdad.
-- =====================================================================================
SELECT  'turno_clave' AS tipo,
        'un batazo que decidió un juego' AS gesta,
        'bateador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        822764 AS universo,
        'Dio el batazo que decidió el juego contra {rival_nombre}, ante {oponente}: {detalle}.' AS plantilla,
        t.mlb_id, t.nombre, t.fecha, t.temporada, t.game_id, t.event_id, t.game_type,
        t.equipo, t.rival, t.en_casa,
        1 AS signo,
        t.wpa AS magnitud,
        t.wpa AS wpa_jugador,
        t.li AS li_max,
        -- SIN LA CIFRA DE LEVERAGE. Decía «con la tensión 4,1 veces la de un turno corriente», que es
        -- exacto y no significa nada para quien lee: obliga a saber qué es el LI y contra qué se
        -- compara. El dato sigue en la columna `li_max` para quien quiera ordenar o filtrar; lo que
        -- cambia es lo que se PUBLICA. La tensión ya está garantizada por el propio corte del
        -- detector —`li >= 2`— así que la frase no tiene que demostrarla, solo nombrarla.
        'en el ' + t.inning_txt + CASE WHEN t.outs = 0 THEN ', sin outs' WHEN t.outs = 1 THEN ', con 1 out' ELSE ', con ' + CAST(t.outs AS varchar(1)) + ' outs' END + ', con el juego en la línea' AS detalle,
        t.equipo_nombre, t.rival_nombre, t.oponente
FROM    #turnos t
WHERE   t.li >= 2 AND t.wpa >= 0.40;
