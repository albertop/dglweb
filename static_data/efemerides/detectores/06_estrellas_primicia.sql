-- =====================================================================================
-- EL PRIMER DOMINICANO EN ABRIR CADA POSICIÓN EN UN JUEGO DE ESTRELLAS.
--
-- Es el gemelo de `89_primero_posicion` —que hace lo mismo en temporada regular— pero en el escenario
-- donde abrir significa que te eligieron el mejor de la liga en tu puesto.
--
-- Medido, las aperturas dominicanas por puesto en 283 apariciones:
--
--     jardines     34        tercera base  19        segunda base  15
--     campocorto   14        primera base  12        lanzador       6
--     receptor      1
--
-- SE ABRE EL JARDÍN EN TRES, no en uno: izquierdo, central y derecho son tres elecciones distintas y
-- juntarlas perdería dos primicias. Con `89_primero_posicion` se hizo igual.
--
-- EL RECEPTOR TIENE UNA SOLA APERTURA EN LA HISTORIA, así que esa fila es a la vez la primera y la
-- única. El detector no necesita saberlo: `situar = 1` y el motor dirá «es el único dominicano».
--
-- `F_<pos>_GS` es «juegos ABIERTOS en esa posición», no jugados. Un dominicano que entra de relevo en
-- el sexto no cuenta, y es lo correcto: la primicia es haber sido ELEGIDO titular.
--
-- GRANO: la apertura en un Juego de Estrellas. `N` = 283, las apariciones dominicanas. Es el mismo
-- universo propio que usa `87_estrellas_actuacion`, y por la misma razón — lo raro se mide dentro del
-- Juego de Estrellas, no contra los juegos de temporada regular.
-- =====================================================================================
WITH d AS (
    SELECT  m.mlbID AS mlb_id, m.nameList AS nombre, a.PLAYER_ID, a.GAME_ID,
            CAST(a.GAME_DT AS date) AS fecha, a.SEASON, a.TEAM_ID, a.OPPONENT_ID, a.HOME_FL,
            a.F_P_GS, a.F_C_GS, a.F_1B_GS, a.F_2B_GS, a.F_3B_GS, a.F_SS_GS,
            a.F_LF_GS, a.F_CF_GS, a.F_RF_GS
    FROM    dbo.retroDailyAS a
    INNER JOIN dbo.dglMaster m ON m.retroID = a.PLAYER_ID
),
-- Una fila por puesto, con la apertura más antigua. `TOP 1` con `ORDER BY fecha, GAME_ID` — el
-- `GAME_ID` desempata los años en que se jugaron dos Juegos de Estrellas (1959-1962).
primeros AS (
    SELECT 'receptor' AS puesto, (SELECT TOP 1 GAME_ID FROM d WHERE F_C_GS >= 1 ORDER BY fecha, GAME_ID) AS game_id, (SELECT TOP 1 PLAYER_ID FROM d WHERE F_C_GS >= 1 ORDER BY fecha, GAME_ID) AS pid
    UNION ALL SELECT 'primera base',     (SELECT TOP 1 GAME_ID FROM d WHERE F_1B_GS >= 1 ORDER BY fecha, GAME_ID), (SELECT TOP 1 PLAYER_ID FROM d WHERE F_1B_GS >= 1 ORDER BY fecha, GAME_ID)
    UNION ALL SELECT 'segunda base',     (SELECT TOP 1 GAME_ID FROM d WHERE F_2B_GS >= 1 ORDER BY fecha, GAME_ID), (SELECT TOP 1 PLAYER_ID FROM d WHERE F_2B_GS >= 1 ORDER BY fecha, GAME_ID)
    UNION ALL SELECT 'tercera base',     (SELECT TOP 1 GAME_ID FROM d WHERE F_3B_GS >= 1 ORDER BY fecha, GAME_ID), (SELECT TOP 1 PLAYER_ID FROM d WHERE F_3B_GS >= 1 ORDER BY fecha, GAME_ID)
    UNION ALL SELECT 'campocorto',       (SELECT TOP 1 GAME_ID FROM d WHERE F_SS_GS >= 1 ORDER BY fecha, GAME_ID), (SELECT TOP 1 PLAYER_ID FROM d WHERE F_SS_GS >= 1 ORDER BY fecha, GAME_ID)
    UNION ALL SELECT 'jardín izquierdo', (SELECT TOP 1 GAME_ID FROM d WHERE F_LF_GS >= 1 ORDER BY fecha, GAME_ID), (SELECT TOP 1 PLAYER_ID FROM d WHERE F_LF_GS >= 1 ORDER BY fecha, GAME_ID)
    UNION ALL SELECT 'jardín central',   (SELECT TOP 1 GAME_ID FROM d WHERE F_CF_GS >= 1 ORDER BY fecha, GAME_ID), (SELECT TOP 1 PLAYER_ID FROM d WHERE F_CF_GS >= 1 ORDER BY fecha, GAME_ID)
    UNION ALL SELECT 'jardín derecho',   (SELECT TOP 1 GAME_ID FROM d WHERE F_RF_GS >= 1 ORDER BY fecha, GAME_ID), (SELECT TOP 1 PLAYER_ID FROM d WHERE F_RF_GS >= 1 ORDER BY fecha, GAME_ID)
    UNION ALL SELECT 'lanzador',         (SELECT TOP 1 GAME_ID FROM d WHERE F_P_GS  >= 1 ORDER BY fecha, GAME_ID), (SELECT TOP 1 PLAYER_ID FROM d WHERE F_P_GS  >= 1 ORDER BY fecha, GAME_ID)
)
SELECT  'estrellas_primicia' AS tipo,
        'la primera apertura dominicana en su posición en un Juego de Estrellas' AS gesta,
        'fildeador'                               AS rol,
        'completa'                                AS cobertura,
        283                                       AS universo,
        -- `situar = 0`: el titular YA dice que fue el primero. Repetirlo con otras palabras sobra.
        0                                         AS situar,
        'Fue el primer dominicano en abrir un Juego de Estrellas como {detalle}.' AS plantilla,
        d.mlb_id, d.nombre, d.fecha, d.SEASON AS temporada, d.GAME_ID AS game_id,
        0                                         AS event_id,
        'A'                                       AS game_type,
        d.TEAM_ID AS equipo, d.OPPONENT_ID AS rival, d.HOME_FL AS en_casa,
        1                                         AS signo,
        -- Los años transcurridos: cuanto más atrás, más historia. Igual que en `89_primero_posicion`.
        YEAR(GETDATE()) - d.SEASON                AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        p.puesto                                  AS detalle,
        ''                                        AS equipo_nombre,
        ''                                        AS rival_nombre,
        ''                                        AS oponente
FROM    primeros p
INNER JOIN d ON d.GAME_ID = p.game_id AND d.PLAYER_ID = p.pid;

-- =====================================================================================
-- LA LISTA — «¿quién fue el primer dominicano en abrir cada puesto en el Juego de Estrellas?»
-- =====================================================================================
/*
WITH d AS (
    SELECT m.nameList, CAST(a.GAME_DT AS date) AS fecha,
           a.F_P_GS, a.F_C_GS, a.F_1B_GS, a.F_2B_GS, a.F_3B_GS, a.F_SS_GS,
           a.F_LF_GS, a.F_CF_GS, a.F_RF_GS
    FROM   dbo.retroDailyAS a INNER JOIN dbo.dglMaster m ON m.retroID = a.PLAYER_ID
)
SELECT 'receptor' AS puesto, (SELECT TOP 1 nameList FROM d WHERE F_C_GS >= 1 ORDER BY fecha) AS jugador, (SELECT TOP 1 fecha FROM d WHERE F_C_GS >= 1 ORDER BY fecha) AS fecha
UNION ALL SELECT 'primera base',     (SELECT TOP 1 nameList FROM d WHERE F_1B_GS >= 1 ORDER BY fecha), (SELECT TOP 1 fecha FROM d WHERE F_1B_GS >= 1 ORDER BY fecha)
UNION ALL SELECT 'segunda base',     (SELECT TOP 1 nameList FROM d WHERE F_2B_GS >= 1 ORDER BY fecha), (SELECT TOP 1 fecha FROM d WHERE F_2B_GS >= 1 ORDER BY fecha)
UNION ALL SELECT 'tercera base',     (SELECT TOP 1 nameList FROM d WHERE F_3B_GS >= 1 ORDER BY fecha), (SELECT TOP 1 fecha FROM d WHERE F_3B_GS >= 1 ORDER BY fecha)
UNION ALL SELECT 'campocorto',       (SELECT TOP 1 nameList FROM d WHERE F_SS_GS >= 1 ORDER BY fecha), (SELECT TOP 1 fecha FROM d WHERE F_SS_GS >= 1 ORDER BY fecha)
UNION ALL SELECT 'jardin izquierdo', (SELECT TOP 1 nameList FROM d WHERE F_LF_GS >= 1 ORDER BY fecha), (SELECT TOP 1 fecha FROM d WHERE F_LF_GS >= 1 ORDER BY fecha)
UNION ALL SELECT 'jardin central',   (SELECT TOP 1 nameList FROM d WHERE F_CF_GS >= 1 ORDER BY fecha), (SELECT TOP 1 fecha FROM d WHERE F_CF_GS >= 1 ORDER BY fecha)
UNION ALL SELECT 'jardin derecho',   (SELECT TOP 1 nameList FROM d WHERE F_RF_GS >= 1 ORDER BY fecha), (SELECT TOP 1 fecha FROM d WHERE F_RF_GS >= 1 ORDER BY fecha)
UNION ALL SELECT 'lanzador',         (SELECT TOP 1 nameList FROM d WHERE F_P_GS  >= 1 ORDER BY fecha), (SELECT TOP 1 fecha FROM d WHERE F_P_GS  >= 1 ORDER BY fecha)
ORDER BY fecha;
*/
