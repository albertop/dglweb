-- =====================================================================================
-- EL CLUB DE LOS 30-30: treinta jonrones y treinta bases robadas en la misma temporada.
--
-- Medido: 18 temporadas dominicanas. Es la marca clásica del jugador completo — poder y piernas, que
-- casi nunca vienen en el mismo hombre.
--
--     Alfonso Soriano   2002 (39/41)  2003 (38/35)  2005 (36/30)  2006 (46/41)
--     José Ramírez      2018 (39/34)  2024 (39/41)  2025 (30/44)
--     Sammy Sosa        1993 (33/36)  1995 (36/34)
--     Vladimir Guerrero 2001 (34/37)  2002 (39/40)
--     Raúl Mondesí      1997 (30/32)  1999 (33/36)
--     Julio Rodríguez   2023 (32/37)  2025 (32/30)
--     Alex Rodríguez    1998 (42/46)  Hanley Ramírez 2008 (33/35)  Juan Soto 2025 (43/38)
--
-- LA FECHA ES LA DEL DÍA EN QUE SE COMPLETÓ, no la del jonrón 30 ni la del robo 30 por separado. La
-- marca se cierra cuando llega el segundo de los dos, y ese es el día del que habla la efeméride.
-- Por eso se busca el PRIMER juego de la temporada en que los dos acumulados ya pasaron de 30, en
-- vez de un cruce de una sola columna como en los demás hitos de temporada.
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
    WHERE   t.hr_ac >= 30 AND t.sb_ac >= 30
)
SELECT  'hito_3030' AS tipo,
        'una temporada de 30+ jonrones y 30+ robos' AS gesta,
        'bateador' AS rol,
        'completa' AS cobertura,
        292948 AS universo,
        1 AS situar,
        -- El titular cierra con los totales del año, que es lo que distingue un 30-30 justo de los
        -- 46-41 de Soriano.
        'Completó el 30-30 contra {rival_nombre}: cerró la temporada con {detalle}.' AS plantilla,
        c.mlb_id, c.nombre, c.fecha, c.temporada, c.game_id,
        0 AS event_id,
        'R' AS game_type,
        c.equipo, c.rival, c.en_casa,
        1 AS signo,
        -- Cuánto se pasó de la marca, sumando las dos patas: un 46-41 pesa más que un 30-30 raspado.
        c.hr_tot + c.sb_tot AS magnitud,
        NULL AS wpa_jugador,
        NULL AS li_max,
        CAST(c.hr_tot AS varchar(3)) + ' jonrones y ' + CAST(c.sb_tot AS varchar(3)) + ' robos' AS detalle,
        c.equipo_nombre, c.rival_nombre,
        '' AS oponente
FROM    cruce c
WHERE   c.rn = 1;

-- =====================================================================================
-- LA LISTA — «¿qué dominicanos han hecho 30-30?»
-- =====================================================================================
/*
SELECT  m.nameList AS jugador, r.SEASON AS temporada,
        SUM(r.B_HR) AS jonrones, SUM(r.B_SB) AS robos
FROM    dbo.retroDailyReg r
INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
GROUP BY m.nameList, r.SEASON
HAVING  SUM(r.B_HR) >= 30 AND SUM(r.B_SB) >= 30
ORDER BY jonrones DESC, robos DESC;
*/
