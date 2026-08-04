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
