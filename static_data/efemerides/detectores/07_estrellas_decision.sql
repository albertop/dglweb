-- =====================================================================================
-- GANÓ, PERDIÓ O SALVÓ UN JUEGO DE ESTRELLAS. Medido: 11 veces, y es la lista completa.
--
--     GANARON (6)     1962 Juan Marichal     1964 Juan Marichal     1998 Bartolo Colón
--                     1999 Pedro Martínez    2022 Framber Valdez    2023 Camilo Doval
--     PERDIERON (3)   1983 Mario Melvin Soto 2016 Johnny Cueto      2023 Félix Bautista
--     SALVARON (2)    2022 Emmanuel Clase    2024 Emmanuel Clase
--
-- LA DERROTA ENTRA, Y NO COMO DESHONRA. `signo = +1` para las tres: al Juego de Estrellas no se llega
-- por casualidad, y cargar con la decisión —para bien o para mal— significa que el manager te puso en
-- el momento que decidía. La derrota de Marichal no existe; la de Pedro tampoco. Que Mario Soto
-- perdiera el de 1983 es historia dominicana igual que las seis victorias.
--
-- SE FUSIONA CON `87_estrellas_actuacion`, que ya dispara con `P_W` o `P_SV`. Coinciden en el mismo
-- jugador y el mismo juego, así que la fusión (sección 7) se queda con este —n = 11 contra n = 32, o
-- sea más rareza— y el otro pasa a etiqueta. Es lo correcto: «ganó el Juego de Estrellas» es más
-- específico que «se lució en el Juego de Estrellas».
--
-- Las derrotas NO las cubría ningún detector hasta ahora: `87` solo mira jonrones, hits, victorias y
-- salvados. Estas tres filas son nuevas de verdad.
--
-- GRANO: la aparición en un Juego de Estrellas. `N` = 283.
-- =====================================================================================
SELECT  'estrellas_decision' AS tipo,
        'una decisión en el Juego de Estrellas' AS gesta,
        'lanzador'                                AS rol,
        'completa'                                AS cobertura,
        283                                       AS universo,
        1                                         AS situar,
        'Se llevó la {detalle} del Juego de Estrellas.' AS plantilla,
        m.mlbID                                   AS mlb_id,
        m.nameList                                AS nombre,
        CAST(a.GAME_DT AS date)                   AS fecha,
        a.SEASON                                  AS temporada,
        a.GAME_ID                                 AS game_id,
        0                                         AS event_id,
        'A'                                       AS game_type,
        a.TEAM_ID                                 AS equipo,
        a.OPPONENT_ID                             AS rival,
        a.HOME_FL                                 AS en_casa,
        1                                         AS signo,
        -- Ganar pesa más que salvar, y salvar más que perder. No es un juicio moral: es cuánto se
        -- parece cada cosa a «decidió el juego».
        (a.P_W * 3) + (a.P_SV * 2) + a.P_L        AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        CASE WHEN a.P_W  = 1 THEN 'victoria'
             WHEN a.P_SV = 1 THEN 'salvada'
             ELSE 'derrota' END                   AS detalle,
        ''                                        AS equipo_nombre,
        ''                                        AS rival_nombre,
        ''                                        AS oponente
FROM    dbo.retroDailyAS a
INNER JOIN dbo.dglMaster m ON m.retroID = a.PLAYER_ID
WHERE   a.P_W = 1 OR a.P_L = 1 OR a.P_SV = 1;

-- =====================================================================================
-- LA LISTA — «¿qué dominicanos han decidido un Juego de Estrellas?»
-- =====================================================================================
/*
SELECT  m.nameList AS jugador, a.SEASON AS temporada,
        CASE WHEN a.P_W = 1 THEN 'ganó' WHEN a.P_SV = 1 THEN 'salvó' ELSE 'perdió' END AS decision,
        a.P_OUT / 3.0 AS entradas, a.P_SO AS ponches, a.P_ER AS limpias
FROM    dbo.retroDailyAS a
INNER JOIN dbo.dglMaster m ON m.retroID = a.PLAYER_ID
WHERE   a.P_W = 1 OR a.P_L = 1 OR a.P_SV = 1
ORDER BY a.SEASON;
*/
