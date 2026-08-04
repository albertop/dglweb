-- =====================================================================================
-- EL PRELUDIO: las tablas de apoyo que TODOS los detectores usan.
--
-- NO ES UN DETECTOR. El motor corre los archivos que empiezan por `_` antes que los demás y NO les
-- exige el contrato: no devuelven efemérides, dejan tablas temporales puestas. Como el motor usa una
-- sola conexión para toda la corrida, las `#tablas` siguen vivas para el resto.
--
-- POR QUÉ ACÁ Y NO COPIADO EN CADA DETECTOR. Resolver el nombre de un equipo y el de un lanzador
-- rival hace falta en casi los 63. Copiado, sería el mismo bloque sesenta y tres veces —y sesenta y
-- tres sitios donde arreglar la regla de nombres el día que cambie—. Acá se escribe una vez y
-- agregar un detector sigue siendo tocar UN archivo, que es la promesa del diseño (sección 8).
-- =====================================================================================

-- --- Los equipos, con el nombre QUE TENÍAN ESE DÍA ------------------------------------
-- SE USAN LAS DOS TABLAS, y cada una aporta lo que la otra no tiene.
--
-- `retroTeams_6d` es la buena: 124 filas para 53 códigos, con `firstGame`/`lastGame`, así que da el
-- nombre DE LA ÉPOCA. Sin ella, un no-hitter de 2011 salía «contra Cleveland Guardians» — y en 2011
-- eran los Indians:
--
--     CLE  Naps       1903-1914      TBA  Devil Rays  1998-2007
--     CLE  Indians    1915-2021      TBA  Rays        2008-
--     CLE  Guardians  2022-          ANA  Anaheim Angels 1997-2004, Los Angeles Angels 2005-
--
-- `lastGame = 1899-12-30` NO es una fecha: es el centinela de «equipo vigente» (confirmado por el
-- dueño). Se traduce a 9999-12-31 para que el `BETWEEN` funcione.
--
-- `retroTeams` es la de respaldo: 292 códigos, mucha más cobertura pero un solo nombre por código.
-- Hace falta porque a la de eras le faltan CUATRO códigos que los dominicanos sí pisaron — medido
-- sobre 158.127 combinaciones equipo-fecha, 212 no resolvían:
--
--     ATH  Sacramento Athletics  2025      (la mudanza de Oakland, aún no está en la de eras)
--     NY6  New York Cubans       1935-49   ┐
--     ASE  East All Stars        1933-62   ├ Ligas Negras
--     NAS  North All Stars       1944-45   ┘
--
-- Con las dos, la cobertura es del 100 % y la exactitud de época se conserva donde existe. Cero
-- ambigüedades: se comprobó que ninguna fecha casa con dos filas.
IF OBJECT_ID('tempdb..#equipos') IS NOT NULL DROP TABLE #equipos;

SELECT  t6.teamId                                                       AS codigo,
        t6.firstGame                                                    AS desde,
        CASE WHEN t6.lastGame < t6.firstGame THEN '9999-12-31' ELSE t6.lastGame END AS hasta,
        LTRIM(RTRIM(COALESCE(t6.location,'') + ' ' + COALESCE(t6.nickname,''))) AS nombre
INTO    #equipos
FROM    dbo.retroTeams_6d t6

UNION ALL

-- Solo los códigos que la de eras NO tiene. El rango sale de las temporadas, que para estos casos
-- alcanza: son equipos sin cambios de nombre dentro de su vida.
SELECT  t.team,
        DATEFROMPARTS(t.firstSeason, 1, 1),
        DATEFROMPARTS(t.lastSeason, 12, 31),
        LTRIM(RTRIM(COALESCE(t.city,'') + ' ' + COALESCE(t.nickname,'')))
FROM    dbo.retroTeams t
WHERE   NOT EXISTS (SELECT 1 FROM dbo.retroTeams_6d x WHERE x.teamId = t.team);

CREATE CLUSTERED INDEX ix_equipos ON #equipos(codigo, desde, hasta);

-- --- Los nombres de CUALQUIER pelotero, dominicano o no -------------------------------
-- LA PRECEDENCIA ES DEL DUEÑO Y NO ES CAPRICHO: si el jugador está en `dglMaster` se usa su
-- `nameList`; si no, el `nickname + last` de `retroMaster`.
--
-- La razón se ve en los datos: `retroMaster` es una fuente en inglés y escribe «German» y
-- «Rodriguez» SIN ACENTO. El maestro dominicano tiene la grafía correcta, y en un sitio dominicano
-- escribir mal el apellido de Domingo Germán no es un detalle.
--
-- Para los de fuera, `nickname` antes que `first` porque es como se les conoce: `retroMaster` guarda
-- «Lynn Nolan» en `first` y «Nolan» en `nickname` para Nolan Ryan, y «Sanford»/«Sandy» para Koufax.
-- Hay 1.126 filas sin `nickname` de 26.966, y ahí cae a `first`.
IF OBJECT_ID('tempdb..#nombres') IS NOT NULL DROP TABLE #nombres;
SELECT  rm.playerID                                                 AS retro_id,
        COALESCE(
            dm.nameList,
            LTRIM(RTRIM(COALESCE(NULLIF(rm.nickname,''), rm.first, '') + ' ' + COALESCE(rm.last,'')))
        )                                                           AS nombre,
        CASE WHEN dm.mlbID IS NOT NULL THEN 1 ELSE 0 END            AS es_dominicano
INTO    #nombres
FROM    dbo.retroMaster rm
LEFT JOIN dbo.dglMaster dm ON dm.retroID = rm.playerID;

CREATE UNIQUE CLUSTERED INDEX ix_nombres ON #nombres(retro_id);

-- --- Los abridores de cada juego ------------------------------------------------------
-- Para una gesta de BATEO de juego completo —un ciclo, cinco hits— «contra qué lanzador» no tiene
-- respuesta exacta: los cuatro batazos pueden ser contra cuatro lanzadores distintos. Lo que sí se
-- puede decir con verdad es contra quién ABRIÓ el rival, que es como se cuenta un juego.
--
-- Las gestas de EVENTO no usan esto: ahí `r24Events.PITCHER_ID` da el lanzador exacto del turno, que
-- es mejor. Un walk-off se cuenta contra quien lo permitió, no contra quien abrió.
IF OBJECT_ID('tempdb..#abridores') IS NOT NULL DROP TABLE #abridores;
SELECT  g.GAME_ID              AS game_id,
        g.AWAY_START_PIT_ID    AS abridor_visita,
        g.HOME_START_PIT_ID    AS abridor_casa
INTO    #abridores
FROM    dbo.retroGamesReg g
UNION ALL
SELECT  gp.GAME_ID, gp.AWAY_START_PIT_ID, gp.HOME_START_PIT_ID
FROM    dbo.retroGamesPost gp;

CREATE UNIQUE CLUSTERED INDEX ix_abridores ON #abridores(game_id);

-- --- EL GRANO DE JUEGO, ya armado -----------------------------------------------------
-- La línea de cada dominicano en cada juego, con el contexto y el WPA ya resueltos.
--
-- POR QUÉ ESTO ES LO QUE MÁS PAGA. Sin ella, cada uno de los ~30 detectores de juego repetía lo
-- mismo: unir `retroDailyReg` con `retroDailyPost`, entrar a `dglMaster`, agregar 16 millones de
-- eventos para sacar el WPA, y resolver equipos y abridores. Con ella, un detector es un `SELECT`
-- con un `WHERE` — y el trabajo caro se hace UNA vez para toda la corrida en vez de treinta.
--
-- El nombre del jugador sale de `nameList`, siempre (ver docs/EFEMERIDES.md 3.0).
IF OBJECT_ID('tempdb..#juegos') IS NOT NULL DROP TABLE #juegos;

WITH d AS (
    SELECT r.PLAYER_ID, r.GAME_ID, r.GAME_DT, r.SEASON, r.TEAM_ID, r.OPPONENT_ID, r.HOME_FL, 'R' AS gt,
           r.B_AB, r.B_H, r.B_2B, r.B_3B, r.B_HR, r.B_RBI, r.B_R, r.B_BB, r.B_SO, r.B_SB, r.B_CS,
           r.B_TB, r.B_HP, r.B_GDP,
           r.P_G, r.P_GS, r.P_CG, r.P_SHO, r.P_SV, r.P_W, r.P_OUT, r.P_H, r.P_R, r.P_ER,
           r.P_BB, r.P_HP, r.P_SO, r.P_GDP, r.P_PITCH
    FROM   dbo.retroDailyReg r
    INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
    UNION ALL
    SELECT p.PLAYER_ID, p.GAME_ID, p.GAME_DT, p.SEASON, p.TEAM_ID, p.OPPONENT_ID, p.HOME_FL, 'P',
           p.B_AB, p.B_H, p.B_2B, p.B_3B, p.B_HR, p.B_RBI, p.B_R, p.B_BB, p.B_SO, p.B_SB, p.B_CS,
           p.B_TB, p.B_HP, p.B_GDP,
           p.P_G, p.P_GS, p.P_CG, p.P_SHO, p.P_SV, p.P_W, p.P_OUT, p.P_H, p.P_R, p.P_ER,
           p.P_BB, p.P_HP, p.P_SO, p.P_GDP, p.P_PITCH
    FROM   dbo.retroDailyPost p
    INNER JOIN dbo.dglMaster m2 ON m2.retroID = p.PLAYER_ID
),
-- El WPA por juego, de los dos lados. Para el LANZADOR va con el signo cambiado: lo que el bateador
-- le quita a su equipo, el lanzador se lo da al suyo.
wb AS (SELECT GAME_ID, BATTER_ID  AS pid, SUM(WPA) AS wpa, MAX(LI) AS li FROM dbo.r24Events WHERE BAT_EVENT_FL = 1 GROUP BY GAME_ID, BATTER_ID),
wp AS (SELECT GAME_ID, PITCHER_ID AS pid, -SUM(WPA) AS wpa, MAX(LI) AS li FROM dbo.r24Events WHERE BAT_EVENT_FL = 1 GROUP BY GAME_ID, PITCHER_ID)
SELECT  d.PLAYER_ID, m.mlbID AS mlb_id, m.nameList AS nombre,
        d.GAME_ID AS game_id, CAST(d.GAME_DT AS date) AS fecha, d.SEASON AS temporada, d.gt AS game_type,
        d.TEAM_ID AS equipo, d.OPPONENT_ID AS rival, d.HOME_FL AS en_casa,
        COALESCE(eq.nombre, '') AS equipo_nombre,
        COALESCE(ri.nombre, '') AS rival_nombre,
        -- NO HAY ABRIDOR RIVAL ACÁ, Y ES DELIBERADO.
        --
        -- Una gesta de este grano se acumula A LO LARGO DE TODO EL JUEGO: un ciclo son cuatro
        -- batazos que pueden ser contra cuatro lanzadores distintos, y siete empujadas se reparten
        -- entre el abridor y el bullpen. Nombrar al abridor da a entender que la gesta fue contra él,
        -- y eso es falso — lo señaló el dueño el 2026-08-03 al ver «Empujó 7 carreras ante el
        -- abridor X».
        --
        -- El lanzador SOLO se nombra en las gestas de EVENTO, donde `r24Events.PITCHER_ID` dice
        -- exactamente contra quién fue ese turno.
        wb.wpa AS wpa_bat, wp.wpa AS wpa_pit,
        COALESCE(wb.li, wp.li) AS li_max,
        d.B_AB, d.B_H, d.B_2B, d.B_3B, d.B_HR, d.B_RBI, d.B_R, d.B_BB, d.B_SO, d.B_SB, d.B_CS,
        d.B_TB, d.B_HP, d.B_GDP,
        -- El sencillo no existe como columna en Retrosheet: se deduce restando extrabases a los hits.
        (d.B_H - d.B_2B - d.B_3B - d.B_HR) AS B_1B,
        d.P_G, d.P_GS, d.P_CG, d.P_SHO, d.P_SV, d.P_W, d.P_OUT, d.P_H, d.P_R, d.P_ER,
        d.P_BB, d.P_HP, d.P_SO, d.P_GDP, d.P_PITCH
INTO    #juegos
FROM    d
INNER JOIN dbo.dglMaster m ON m.retroID = d.PLAYER_ID
LEFT  JOIN #equipos   eq ON eq.codigo = d.TEAM_ID     AND d.GAME_DT BETWEEN eq.desde AND eq.hasta
LEFT  JOIN #equipos   ri ON ri.codigo = d.OPPONENT_ID AND d.GAME_DT BETWEEN ri.desde AND ri.hasta
LEFT  JOIN wb ON wb.GAME_ID = d.GAME_ID AND wb.pid = d.PLAYER_ID
LEFT  JOIN wp ON wp.GAME_ID = d.GAME_ID AND wp.pid = d.PLAYER_ID;

CREATE CLUSTERED INDEX ix_juegos ON #juegos(PLAYER_ID, game_id);
