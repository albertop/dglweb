-- =====================================================================================
-- El «sombrero dorado»: ponchado cuatro veces. Medido: 499 veces, 172 jugadores. Rareza 152.
--
-- LOS TIERS SON EXACTOS, NO ACUMULATIVOS: cinco ponches es PLATINO, no dorado. Son escalones, no
-- umbrales. Ver docs/EFEMERIDES.md 5.1.14.
--
-- Es el detector mas ruidoso del inventario (4,30 por temporada) y entra igual: tiene nombre
-- reconocible y su rareza baja lo deja donde no desplaza a nadie.
--
-- Sale de `#juegos` (preludio `_00_comun.sql`). Sin abridor rival: gesta de juego completo.
-- =====================================================================================
SELECT  'sombrero_dorado' AS tipo,
        'bateador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        292948 AS universo,
        'Se puso el sombrero dorado contra {rival_nombre}: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0 AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        -1 AS signo,
        j.B_SO AS magnitud,
        NULL AS wpa_jugador,
        j.li_max,
        'ponchado 4 veces en ' + CAST(j.B_AB AS varchar(2)) + ' turnos' AS detalle,
        j.equipo_nombre, j.rival_nombre,
        '' AS oponente
FROM    #juegos j
WHERE   j.B_SO = 4;
