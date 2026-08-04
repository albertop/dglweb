-- =====================================================================================
-- TRES O MAS TOQUES DE SACRIFICIO en un juego. Medido: 6 veces, 5 jugadores. Rareza 515.
--
-- EL UMBRAL SE CALCULO. Con 2 serian 243 juegos (2,09 por temporada) y un toque no es una gesta: es
-- una jugada tactica que el manager pide. Con 3 son seis en 116 temporadas.
--
--     2 toques    243   2,09 por temporada
--     3 toques      6   0,05
--     4 toques      1   el record
--
-- El record es de FELIX FERMIN, 1989-08-22, con CUATRO. Sube solo por magnitud. Los otros cinco:
-- Jose De Leon (1988), Fermin otra vez (1991), Pedro Martinez (1996), Deivi Cruz (2000) y Placido
-- Polanco (2001) — dos de ellos lanzadores, que es donde el toque tiene mas sentido.
--
-- Sale de `#juegos` (preludio `_00_comun.sql`). Sin abridor rival: gesta de juego completo.
-- =====================================================================================
SELECT  'toques3' AS tipo,
        '3+ toques de sacrificio en un juego' AS gesta,
        'bateador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        292948 AS universo,
        'Se sacrificó {magnitud} veces en el mismo juego contra {rival_nombre}: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0 AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1 AS signo,
        j.B_SH AS magnitud,
        j.wpa_bat AS wpa_jugador,
        j.li_max,
        'en ' + CAST(j.B_AB + j.B_SH AS varchar(2)) + ' veces al plato' AS detalle,
        j.equipo_nombre, j.rival_nombre,
        '' AS oponente
FROM    #juegos j
WHERE   j.B_SH >= 3;
