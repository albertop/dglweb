-- =====================================================================================
-- JONRÓN DENTRO DEL PARQUE.
--
-- Medido: 22 dominicanos desde 2008, de 220 en toda la liga.
--
-- POR QUÉ SALE DE STATCAST Y NO DE RETROSHEET, que cubriría 116 temporadas en vez de 19: porque
-- RETROSHEET NO LO MARCA. Se buscó — de los 327.671 jonrones de `retroEventsReg`, CERO traen
-- «INSIDE» o «ITP» en `EVENT_TX`, y no hay ninguna otra columna que lo distinga. Un jonrón dentro
-- del parque se anota igual que uno por encima de la cerca.
--
-- Statcast sí lo dice, pero en PROSA: el campo `des` es la narración de la jugada y ahí aparece
-- «inside-the-park». Es una fuente de texto libre y por eso se acota con `events = 'home_run'`
-- primero: sin eso, un `des` que mencione la jugada por otro motivo entraría igual.
--
-- COBERTURA PARCIAL: 2008-2026. El motor no publica los totales — sabemos de 22, no cuántos hay.
--
-- GRANO: turnos de bateadores dominicanos EN LA VENTANA DE STATCAST (398.775), no los 822.764 de
-- toda la historia. Numerador y denominador se miden en la misma ventana o la rareza sale mal.
-- =====================================================================================
WITH itp AS (
    SELECT  s.batter                     AS mlb_id,
            CAST(s.game_date AS date)    AS fecha,
            s.game_pk,
            s.inning,
            MIN(s.des)                   AS narracion
    FROM    dbo.scastPitch s
    INNER JOIN dbo.dglMaster m ON m.mlbID = s.batter
    WHERE   s.events = 'home_run'
      AND   s.des LIKE '%inside-the-park%'
    GROUP BY s.batter, CAST(s.game_date AS date), s.game_pk, s.inning
)
SELECT  'hr_dentro_parque'                        AS tipo,
        'un jonrón dentro del parque' AS gesta,
        'bateador'                                AS rol,
        'parcial'                                 AS cobertura,
        1                                         AS situar,
        398775                                    AS universo,
        'Conectó un jonrón dentro del parque contra {rival_nombre}: {detalle}.' AS plantilla,
        i.mlb_id,
        m.nameList                                AS nombre,
        i.fecha,
        p.temporada, p.game_id,
        0                                         AS event_id,
        p.game_type, p.equipo, p.rival, p.en_casa,
        1                                         AS signo,
        1                                         AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        'corrió las cuatro bases, en el '
            + CASE WHEN i.inning >= 10 THEN 'inning ' + CAST(i.inning AS varchar(2))
                   ELSE CASE i.inning WHEN 1 THEN '1er' WHEN 2 THEN '2do' WHEN 3 THEN '3er'
                                      WHEN 4 THEN '4to' WHEN 5 THEN '5to' WHEN 6 THEN '6to'
                                      WHEN 7 THEN '7mo' WHEN 8 THEN '8vo' ELSE '9no' END END AS detalle,
        p.equipo_nombre, p.rival_nombre,
        ''                                        AS oponente
FROM    itp i
INNER JOIN dbo.dglMaster m ON m.mlbID = i.mlb_id
INNER JOIN #puente p ON p.mlb_id = i.mlb_id AND p.fecha = i.fecha;

-- =====================================================================================
-- LA LISTA — «¿quiénes han conectado un jonrón dentro del parque?»
--
-- Se pega tal cual y corre sola. Trae la narración de Statcast, que es de dónde sale el dato.
--
-- OJO AL LEERLA: son los de 2008 en adelante. Los anteriores existen y no se pueden contar — ver la
-- cabecera de este archivo.
-- =====================================================================================
/*
SELECT  m.nameList                    AS jugador,
        CAST(s.game_date AS date)     AS fecha,
        s.inning,
        s.des                         AS narracion
FROM    dbo.scastPitch s
INNER JOIN dbo.dglMaster m ON m.mlbID = s.batter
WHERE   s.events = 'home_run'
  AND   s.des LIKE '%inside-the-park%'
ORDER BY s.game_date;
*/
