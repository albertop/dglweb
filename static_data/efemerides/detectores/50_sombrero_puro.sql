-- =====================================================================================
-- EL SOMBRERO DORADO PURO: cuatro apariciones al plato, cuatro ponches, nada más.
--
-- REEMPLAZA AL `sombrero_dorado` DE ANTES, que contaba cualquier juego de 4 ponches y daba 499 filas
-- —el detector más ruidoso del inventario, 4,30 por temporada—. El dueño lo marcó como demasiado, y
-- tenía razón: ponchar cuatro veces en un juego de cinco o seis apariciones es una mala noche; hacerlo
-- en CUATRO DE CUATRO es no haber tocado la pelota en todo el día.
--
-- Medido:
--
--     4 ponches, cualquier cantidad de apariciones   499 juegos, 172 jugadores   <- el de antes
--     4 ponches en 4 apariciones exactas             229 juegos, 116 jugadores   <- este
--
-- La condición es `B_SO = 4` y además `B_AB = 4` sin boletos, sin pelotazos y sin sacrificios: cuatro
-- veces al plato y cuatro veces de vuelta a la banca. Ni una vez en base.
--
-- SIGUE SIENDO EL DETECTOR MÁS ABUNDANTE del inventario y eso está bien: tiene nombre reconocible
-- —«se puso el sombrero dorado»— y su rareza lo deja tan abajo que nunca desplaza a una gesta de
-- verdad. Funciona como relleno con gracia, que es lo que le falta a un día flojo.
--
-- LOS ESCALONES DE ARRIBA son `51_sombrero_platino` (5 ponches) y `52_sombrero_titanio` (6+, que
-- ningún dominicano ha alcanzado). Son EXACTOS, no acumulativos: en la jerarquía real un juego de
-- cinco ponches es platino, no dorado.
--
-- LA VARIANTE MÁS DURA es `18_sombrero_mismo_lanzador`: los cuatro ponches del MISMO lanzador.
--
-- `signo = -1`: media escala en todo, techo 400. Ver docs/EFEMERIDES.md 4.5.
--
-- GRANO: juego-jugador (292.948).
-- =====================================================================================
SELECT  'sombrero_puro' AS tipo,
        '4 ponches en 4 apariciones' AS gesta,
        'bateador'                                AS rol,
        'completa'                                AS cobertura,
        292948                                    AS universo,
        1                                         AS situar,
        'Se puso el sombrero dorado contra {rival_nombre}: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        -1                                        AS signo,
        4                                         AS magnitud,
        NULL                                      AS wpa_jugador,
        j.li_max,
        'ponchado las cuatro veces que fue al plato, sin llegar a base ni una vez' AS detalle,
        j.equipo_nombre, j.rival_nombre,
        ''                                        AS oponente
FROM    #juegos j
WHERE   j.B_SO = 4
  AND   j.B_AB = 4
  AND   j.B_BB = 0
  AND   j.B_HP = 0
  AND   j.B_SH = 0;

-- =====================================================================================
-- LA LISTA — «¿quiénes se poncharon cuatro veces en cuatro turnos?»
-- =====================================================================================
/*
SELECT  m.nameList AS jugador, CAST(r.GAME_DT AS date) AS fecha, r.TEAM_ID AS equipo,
        r.B_SO AS ponches, r.B_AB AS turnos
FROM    dbo.retroDailyReg r
INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
WHERE   r.B_SO = 4 AND r.B_AB = 4 AND r.B_BB = 0 AND r.B_HP = 0 AND r.B_SH = 0 AND r.B_SF = 0
ORDER BY fecha;
*/
