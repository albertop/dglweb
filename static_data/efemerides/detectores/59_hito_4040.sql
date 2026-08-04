-- =====================================================================================
-- EL 40-40: cuarenta jonrones y cuarenta bases robadas en la misma temporada.
--
-- Medido: DOS temporadas dominicanas, y son la lista entera:
--
--     1998   Alex Rodríguez    42 jonrones / 46 robos
--     2006   Alfonso Soriano   46 jonrones / 41 robos
--
-- En toda la historia de Grandes Ligas el club tiene un puñado de miembros, y dos son dominicanos.
--
-- CONVIVE CON `58_hito_3030` a propósito: quien llega a 40-40 completó antes el 30-30, pero en otro
-- juego y otro día del calendario, así que no se fusionan. Los dos son noticia y cada uno cae donde
-- le toca.
--
-- LA FECHA ES LA DEL DÍA EN QUE SE COMPLETÓ — el segundo de los dos números, no el primero. Mismo
-- método que el 30-30.
--
-- SOLO TEMPORADA REGULAR — ver `_05_temporada.sql`.
--
-- GRANO: juego-jugador (292.948).
-- =====================================================================================
WITH cruce AS (
    SELECT  t.*,
            ROW_NUMBER() OVER (PARTITION BY t.PLAYER_ID, t.temporada
                               ORDER BY t.fecha, t.game_id) AS rn
    FROM    #temporada t
    WHERE   t.hr_ac >= 40 AND t.sb_ac >= 40
)
SELECT  'hito_4040' AS tipo,
        'una temporada de 40+ jonrones y 40+ robos' AS gesta,
        'bateador' AS rol,
        'completa' AS cobertura,
        292948 AS universo,
        1 AS situar,
        'Completó el 40-40 contra {rival_nombre}: cerró la temporada con {detalle}.' AS plantilla,
        c.mlb_id, c.nombre, c.fecha, c.temporada, c.game_id,
        0 AS event_id,
        'R' AS game_type,
        c.equipo, c.rival, c.en_casa,
        1 AS signo,
        c.hr_tot + c.sb_tot AS magnitud,
        NULL AS wpa_jugador,
        NULL AS li_max,
        CAST(c.hr_tot AS varchar(3)) + ' jonrones y ' + CAST(c.sb_tot AS varchar(3)) + ' robos' AS detalle,
        c.equipo_nombre, c.rival_nombre,
        '' AS oponente
FROM    cruce c
WHERE   c.rn = 1;

-- =====================================================================================
-- LA LISTA — los dos 40-40 dominicanos
-- =====================================================================================
/*
SELECT  m.nameList AS jugador, r.SEASON AS temporada,
        SUM(r.B_HR) AS jonrones, SUM(r.B_SB) AS robos
FROM    dbo.retroDailyReg r
INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
GROUP BY m.nameList, r.SEASON
HAVING  SUM(r.B_HR) >= 40 AND SUM(r.B_SB) >= 40
ORDER BY r.SEASON;
*/
