-- =====================================================================================
-- Tres o mas dobles matanzas bateadas. Medido: 10 veces, 10 jugadores. Rareza 245.
--
-- Con umbral 2 serian 549 juegos (4,73 por temporada) y eso no es efemeride. Ningun dominicano ha
-- llegado a 4; en toda la liga solo ha pasado dos veces.
--
-- Sale de `#juegos` (preludio `_00_comun.sql`). Sin abridor rival: gesta de juego completo.
-- =====================================================================================
SELECT  'gidp3' AS tipo,
        'bateador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        292948 AS universo,
        'Bateó para {magnitud} dobles matanzas contra {rival_nombre}: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0 AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        -1 AS signo,
        j.B_GDP AS magnitud,
        NULL AS wpa_jugador,
        j.li_max,
        'en ' + CAST(j.B_AB AS varchar(2)) + ' turnos' AS detalle,
        j.equipo_nombre, j.rival_nombre,
        '' AS oponente
FROM    #juegos j
WHERE   j.B_GDP >= 3;
