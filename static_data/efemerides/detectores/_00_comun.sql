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

-- --- Los equipos, con nombre legible --------------------------------------------------
-- `retroTeams` da la ciudad y el apodo por separado. Comprobado el 2026-08-03: 292 filas y 292
-- códigos distintos, o sea que NINGÚN código se reutiliza — un join simple basta y no hace falta
-- acotar por temporada. Se verificó a propósito, porque la tabla tiene `firstSeason`/`lastSeason` y
-- eso hacía pensar lo contrario.
--
-- ⚠️ LO QUE ESTA TABLA NO PUEDE DAR: EL NOMBRE DE LA ÉPOCA.
--
-- Las MUDANZAS sí tienen código propio, y ahí el nombre sale bien:
--
--     BRO  Brooklyn Dodgers   1890-1957     FLO  Florida Marlins  1993-2011
--     LAN  Los Angeles Dodgers 1958-2025    MIA  Miami Marlins    2012-2025
--
-- Los CAMBIOS DE NOMBRE SIN MUDANZA, no: el código se queda y la tabla guarda un solo nombre.
--
--     CLE  «Cleveland Guardians»    1901-2025   pero fueron Indians hasta 2021
--     TBA  «Tampa Bay Devil Rays»   1998-2025   pero son Rays desde 2008
--
-- Ni siquiera es consistente en cuál de los dos guarda: Guardians es el nuevo, Devil Rays el viejo.
-- El efecto se ve en el archivo: el no-hitter de Ervin Santana de 2011 sale «contra Cleveland
-- Guardians», y en 2011 eran los Indians.
--
-- SE DEJA ASÍ A PROPÓSITO Y NO SE INVENTA UNA TABLA DE RENOMBRAMIENTOS. Los datos del sitio salen de
-- fuentes, no de memoria; una lista de nombres históricos escrita a mano sería exactamente el tipo de
-- dato que este proyecto no se permite. Si hace falta la exactitud de época, el dueño provee la
-- tabla y esto la usa. Mientras tanto la franquicia se identifica bien, que es lo que importa para
-- saber contra quién fue la gesta.
IF OBJECT_ID('tempdb..#equipos') IS NOT NULL DROP TABLE #equipos;
SELECT  t.team                                                      AS codigo,
        LTRIM(RTRIM(COALESCE(t.city,'') + ' ' + COALESCE(t.nickname,''))) AS nombre
INTO    #equipos
FROM    dbo.retroTeams t;

CREATE UNIQUE CLUSTERED INDEX ix_equipos ON #equipos(codigo);

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
