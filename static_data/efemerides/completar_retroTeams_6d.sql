-- =====================================================================================
-- Completar dbo.retroTeams_6d — los Athletics de Sacramento
-- =====================================================================================
--
-- ESTO SE CORRE A MANO, UNA VEZ, CONTRA DGL. No lo ejecuta el exportador.
--
-- POR QUÉ HACE FALTA
-- ------------------
-- `retroTeams_6d` es la tabla que le da a las efemérides el nombre que el equipo TENÍA ESE DÍA
-- (ver `detectores/_00_comun.sql`). Le faltan códigos que los dominicanos sí pisaron: medido sobre
-- 158.127 combinaciones equipo-fecha, 212 no resolvían, repartidas en cuatro códigos.
--
--     ATH  Sacramento Athletics   115 fechas, 2025
--     NY6  New York Cubans         89 fechas, 1935-1947   ┐
--     ASE  East All Stars           7 fechas, 1940-1945   ├ Ligas Negras
--     NAS  North All Stars          1 fecha,  1943        ┘
--
-- SOLO SE INSERTA `ATH`. Los otros tres NO, y no por pereza:
--
--   * `retroTeams_6d` no tiene NI UNA fila de Ligas Negras — sus ligas son AL, NL, AA y NA. Meterlas
--     sería estirar la tabla más allá de lo que modela.
--   * `retroTeams` dice que la liga de NY6 es **'NN2;NAL'** (dos ligas), y `league` acá es
--     `varchar(2)`: no cabe. No hay valor correcto que poner.
--   * ASE y NAS **no son franquicias**, son equipos de estrellas. No tienen ciudad: jugaron en 17
--     parques distintos entre Nueva Jersey, Michigan, Connecticut, Pensilvania y Luisiana.
--
-- Los tres siguen saliendo bien igual, porque el preludio cae a `retroTeams` cuando el código no
-- está en la de eras. No hay nada roto que arreglar ahí.
--
-- DE DÓNDE SALE CADA VALOR — ninguno es de memoria:
--
--     franchiseID  'OAK'          la línea PHA(1901-1954) -> KC1(1955-1967) -> OAK(1968-) que ya
--                                 está en la tabla; Sacramento la continúa
--     league       'AL'           de `retroTeams`
--     divsion      'W'            de la fila vigente de OAK en esta misma tabla
--     location     'Sacramento'   de `retroTeams.city`
--     nickname     'Athletics'    de `retroTeams.nickname`
--     firstGame    2025-03-27     el PRIMER JUEGO REAL de ATH en `retroGamesReg` (162 juegos)
--     lastGame     1899-12-30     el centinela de «equipo vigente» de esta tabla
--     city/state   Sacramento, CA de `retroBallParks`: ATH juega de local en SAC01, «Sacramento, CA»
-- =====================================================================================

SET XACT_ABORT ON;
BEGIN TRANSACTION;

-- --- 1. Cerrar la fila de Oakland ------------------------------------------------------
-- NO ES OPCIONAL, aunque hoy no rompa ninguna consulta. La fila vigente de OAK dice `lastGame =
-- 1899-12-30`, o sea «sigue jugando», y OAK no juega desde el **2024-09-29** — cero juegos en 2025.
-- Dejarla abierta es guardar un dato falso, y el día que alguien pregunte «¿qué equipos hay hoy?»
-- la respuesta va a incluir un equipo que ya no existe.
--
-- El join por código no se confunde —OAK y ATH son códigos distintos— así que esto es corrección,
-- no un arreglo de un fallo.
UPDATE dbo.retroTeams_6d
SET    lastGame = '2024-09-29'
WHERE  teamId   = 'OAK'
  AND  lastGame = '1899-12-30';

-- --- 2. Insertar Sacramento -----------------------------------------------------------
-- El `NOT EXISTS` la hace repetible: correrla dos veces no duplica la fila.
INSERT INTO dbo.retroTeams_6d
       (franchiseID, teamId, league, divsion, location, nickname, altNicknames,
        firstGame, lastGame, city, state)
SELECT 'OAK', 'ATH', 'AL', 'W', 'Sacramento', 'Athletics', NULL,
       '2025-03-27', '1899-12-30', 'Sacramento', 'CA'
WHERE  NOT EXISTS (SELECT 1 FROM dbo.retroTeams_6d WHERE teamId = 'ATH');

COMMIT;

-- =====================================================================================
-- Comprobación — debe devolver la línea completa de la franquicia, sin huecos ni solapes
-- =====================================================================================
SELECT  franchiseID, teamId, league, divsion, location, nickname,
        CONVERT(varchar(10), firstGame, 120) AS desde,
        CASE WHEN lastGame < firstGame THEN '(vigente)' ELSE CONVERT(varchar(10), lastGame, 120) END AS hasta,
        city, state
FROM    dbo.retroTeams_6d
WHERE   franchiseID = 'OAK'
ORDER BY firstGame;
