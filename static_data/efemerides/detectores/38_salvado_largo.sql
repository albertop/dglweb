-- =====================================================================================
-- El salvado LARGO: tres entradas o más para cerrar. Medido: 146 veces, 60 lanzadores. Rareza 362.
--
-- EL UMBRAL SE CALCULO, no se eligió. Los salvados a secas son 5.795 (50 por temporada) y no son
-- efeméride ninguna; con 2 entradas son 411 (3,5 por temporada), todavía ruidosos:
--
--     todos           5.795   50,0 por temporada
--     2+ entradas       411    3,5
--     3+ entradas       146    1,26   <- acá deja de ser rutina
--     4+ entradas        33    0,28
--
-- Con 3 queda en 1,26 por temporada, la misma liga que hits5 (1,32). Los de cuatro entradas suben
-- solos por magnitud, que es P_OUT.
--
-- Sale de `#juegos` (preludio `_00_comun.sql`). Sin abridor rival: gesta de juego completo.
-- =====================================================================================
SELECT  'salvado_largo' AS tipo,
        'lanzador' AS rol,
        'completa' AS cobertura,
        1 AS situar,
        292948 AS universo,
        'Salvó el juego contra {rival_nombre} lanzando {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0 AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1 AS signo,
        j.P_OUT AS magnitud,
        j.wpa_pit AS wpa_jugador,
        j.li_max,
        CAST(j.P_OUT / 3 AS varchar(3)) + CASE j.P_OUT % 3 WHEN 1 THEN '.1' WHEN 2 THEN '.2' ELSE '' END + CASE WHEN j.P_OUT = 3 THEN ' entrada' ELSE ' entradas' END + CASE WHEN j.P_H = 0 THEN ' sin permitir hit' WHEN j.P_ER = 0 THEN ' sin carreras limpias' ELSE '' END AS detalle,
        j.equipo_nombre, j.rival_nombre,
        '' AS oponente
FROM    #juegos j
WHERE   j.P_SV >= 1 AND j.P_OUT >= 9;
