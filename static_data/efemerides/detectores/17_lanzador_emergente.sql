-- =====================================================================================
-- UN LANZADOR SALE A BATEAR DE EMERGENTE. Medido: 22 veces, 15 lanzadores.
--
-- No es que le tocara batear por estar en el juego: es que el manager lo MANDÓ al plato a decidir un
-- turno, teniendo banco. O confiaba mucho en su madero, o ya no le quedaba nadie.
--
-- SE DETECTA CON `B_G_PH`, la columna del game log que marca «juegos como bateador emergente». No hay
-- que deducir nada: Retrosheet ya lo trae.
--
-- QUIÉN ES «LANZADOR» SE MIDE, NO SE LISTA: más del 90 % de sus juegos de carrera lanzando. Mismo
-- criterio que `15_lanzador_en_posicion` y `16_lanzador_jonron`.
--
-- POR QUÉ NO SE CONFUNDE CON `16_lanzador_jonron`: aquel cuenta al lanzador que batea en su propio
-- turno de la alineación —cosa normal antes del bateador designado universal— y este cuenta al que
-- entra a batear POR OTRO. Son dos costumbres distintas y las dos se están extinguiendo.
--
-- GRANO: juego-jugador (292.948).
-- =====================================================================================
WITH perfil AS (
    SELECT  j.PLAYER_ID,
            COUNT(1) AS juegos,
            SUM(CASE WHEN j.P_G >= 1 THEN 1 ELSE 0 END) AS juegos_lanzando
    FROM    #juegos j
    GROUP BY j.PLAYER_ID
),
-- `B_G_PH` no viaja en `#juegos` — no la necesitaba ningún detector hasta ahora.
emergente AS (
    SELECT r.PLAYER_ID, r.GAME_ID, r.B_G_PH, r.B_H, r.B_AB, r.B_HR, r.B_RBI
    FROM   dbo.retroDailyReg r

)
SELECT  'lanzador_emergente' AS tipo,
        'un turno de bateador emergente siendo lanzador' AS gesta,
        '' AS participantes,
        'bateador'                                AS rol,
        'completa'                                AS cobertura,
        288826                                    AS universo,
        1                                         AS situar,
        'Lo mandaron a batear de emergente siendo lanzador, contra {rival_nombre}: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                         AS signo,
        -- Que le saliera bien pesa más que el simple hecho de ir.
        1 + (e.B_H * 2) + (e.B_HR * 3)            AS magnitud,
        NULL                                      AS wpa_jugador,
        j.li_max,
        CASE WHEN e.B_HR >= 1 THEN 'y conectó jonrón'
             WHEN e.B_H  >= 1 THEN 'y dio hit'
             WHEN e.B_AB >= 1 THEN 'y no pudo con el turno'
             ELSE 'aunque no llegó a completar el turno' END AS detalle,
        j.equipo_nombre, j.rival_nombre,
        ''                                        AS oponente
FROM    #juegos j
INNER JOIN perfil    p ON p.PLAYER_ID = j.PLAYER_ID
INNER JOIN emergente e ON e.PLAYER_ID = j.PLAYER_ID AND e.GAME_ID = j.game_id
WHERE   e.B_G_PH >= 1
  AND   p.juegos_lanzando * 10 > p.juegos * 9;

-- =====================================================================================
-- LA LISTA — «¿qué lanzadores dominicanos han bateado de emergente?»
-- =====================================================================================
/*
WITH d AS (
    SELECT r.PLAYER_ID, r.GAME_ID, r.GAME_DT, r.P_G, r.B_G_PH, r.B_H, r.B_AB, r.B_HR
    FROM   dbo.retroDailyReg r INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
    UNION ALL
    SELECT p.PLAYER_ID, p.GAME_ID, p.GAME_DT, p.P_G, p.B_G_PH, p.B_H, p.B_AB, p.B_HR
    FROM   dbo.retroDailyPost p INNER JOIN dbo.dglMaster m ON m.retroID = p.PLAYER_ID
),
perfil AS (SELECT PLAYER_ID, COUNT(1) AS juegos,
                  SUM(CASE WHEN P_G >= 1 THEN 1 ELSE 0 END) AS lanzando
           FROM d GROUP BY PLAYER_ID)
SELECT  CAST(d.GAME_DT AS date) AS fecha, m.nameList AS lanzador,
        d.B_AB AS turnos, d.B_H AS hits, d.B_HR AS jonrones
FROM    d
INNER JOIN perfil pf ON pf.PLAYER_ID = d.PLAYER_ID
INNER JOIN dbo.dglMaster m ON m.retroID = d.PLAYER_ID
WHERE   d.B_G_PH >= 1 AND pf.lanzando * 10 > pf.juegos * 9
ORDER BY fecha;
*/
