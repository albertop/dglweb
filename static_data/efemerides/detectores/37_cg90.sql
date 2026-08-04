-- =====================================================================================
-- Juego completo de menos de 90 lanzamientos. Medido: 8 veces, 7 lanzadores. Rareza 500.
--
-- DOS FILTROS QUE NO SON OPCIONALES, y sin ellos da 19 en vez de 8:
--
--   temporada >= 1989   el conteo de lanzamientos solo vale desde 1989 (regla del dueño): de los
--                       197 juegos completos dominicanos de los sesenta, solo 14 traen conteo.
--   P_OUT >= 27         P_CG incluye los acortados por lluvia. Sin esto entraba un juego de Ivan
--                       Nova de 57 lanzamientos que son 16 outs, o sea 5.1 entradas.
--
-- El universo tambien es propio: 251.106 juegos-jugador de 1989 en adelante. Es la regla del grano
-- aplicada al tiempo.
--
-- LA MAGNITUD VA AL REVES: menos lanzamientos es mas gesta, asi que se invierte.
--
-- Sale de `#juegos` (preludio `_00_comun.sql`). Sin abridor rival: gesta de juego completo.
-- =====================================================================================
SELECT  'cg90' AS tipo,
        'lanzador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        251106 AS universo,
        'Despachó a {rival_nombre} en juego completo con solo {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0 AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1 AS signo,
        (90 - j.P_PITCH) AS magnitud,
        j.wpa_pit AS wpa_jugador,
        j.li_max,
        CAST(j.P_PITCH AS varchar(3)) + ' lanzamientos' AS detalle,
        j.equipo_nombre, j.rival_nombre,
        '' AS oponente
FROM    #juegos j
WHERE   j.temporada >= 1989 AND j.P_PITCH > 0 AND j.P_PITCH < 90 AND j.P_OUT >= 27 AND j.P_CG >= 1;
