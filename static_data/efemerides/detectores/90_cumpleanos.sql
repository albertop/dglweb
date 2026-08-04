-- =====================================================================================
-- El cumpleaños.
--
-- GRANO: persona. No lleva `universo` de rareza porque la rareza no significa nada acá — todo el
-- mundo tiene cumpleaños. Corre en escala propia, 0-250, siempre por debajo de cualquier gesta real.
-- Ver docs/EFEMERIDES.md 4.6.
--
-- SE SUPRIME SI EL JUGADOR TIENE `deathDate`. Regla del dueño, y es la razón de que sean 923 filas y
-- no 984: 61 fallecidos quedan fuera. Felicitar a un muerto por su cumpleaños es el tipo de error
-- que un sistema automático comete y una persona no. A esos 61 les toca su aniversario de
-- fallecimiento, que va por `92_fallecimiento.sql`.
--
-- LA FECHA ES LA DEL ANIVERSARIO DE ESTE AÑO, no la de nacimiento: el archivo se consulta por mes y
-- día, y así `mes`/`dia` salen bien sin que el motor tenga que saber que este tipo es distinto. El
-- año de nacimiento sigue en `detalle`.
-- =====================================================================================
SELECT  'cumpleanos'                              AS tipo,
        'persona'                                 AS rol,
        'completa'                                AS cobertura,
        -- `situar = 0`: la frase «uno de los N dominicanos que lo ha logrado» NO aplica a cumplir
        -- años. La primera corrida del motor la publicó igual y salió «Cumple 46 años. Es uno de los
        -- 923 dominicanos que lo ha logrado», que es un disparate. Peor todavía: el bono de relieve
        -- le daba +30 a Fernando Tatís por nacer un 1 de enero —el primero de la lista— y con eso
        -- superaba a Albert Pujols, que tiene tres veces más juegos.
        0                                         AS situar,
        -- El universo son los 984 del maestro. Con `n = 923` la rareza sale ~2, o sea nada: es
        -- correcto y es el punto. El puntaje de esta fila lo pone la magnitud, no la rareza.
        984                                       AS universo,
        'Cumple {detalle}.'                       AS plantilla,
        m.mlbID                                   AS mlb_id,
        m.nameList                                AS nombre,
        DATEFROMPARTS(YEAR(GETDATE()), MONTH(m.birthDate), DAY(m.birthDate)) AS fecha,
        YEAR(m.birthDate)                         AS temporada,
        ''                                        AS game_id,
        0                                         AS event_id,
        '-'                                       AS game_type,
        ''                                        AS equipo,
        ''                                        AS rival,
        0                                         AS en_casa,
        1                                         AS signo,
        -- LA MAGNITUD ES LA HUELLA DEL JUGADOR: juegos de su carrera. Es lo que hace que el
        -- cumpleaños de Pedro Martínez no pese igual que el de alguien con tres juegos, sin que
        -- nadie tenga que mantener una lista de «importantes».
        COALESCE((SELECT COUNT(1) FROM dbo.retroDailyReg r WHERE r.PLAYER_ID = m.retroID), 0) AS magnitud,
        NULL                                      AS wpa_jugador,
        NULL                                      AS li_max,
        CAST(YEAR(GETDATE()) - YEAR(m.birthDate) AS varchar(3)) + ' años' AS detalle
FROM    dbo.dglMaster m
WHERE   m.birthDate IS NOT NULL
  AND   m.deathDate IS NULL;
