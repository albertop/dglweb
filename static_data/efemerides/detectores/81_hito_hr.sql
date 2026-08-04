-- =====================================================================================
-- El jonrón 100, 200, 300… Medido: 137 cruces.
--
-- Sale de `#carrera` (preludio `_02_carrera.sql`), que ya trae el acumulado juego a juego.
--
-- EL CRUCE se detecta con división entera: si el total dividido por el escalón subió respecto
-- del total ANTES de este juego, es que se pasó una marca redonda. Funciona aunque el jugador
-- cruce dos marcas el mismo día — cosa que con escalón 50 y un juego de dos salvados no pasa,
-- pero la fórmula no depende de eso.
--
-- LA MAGNITUD ES LA CIFRA ALCANZADA, no el número de veces. Es lo que hace que el hit 3000 pese
-- más que el hit 500 sin mantener ninguna tabla de importancia: el motor lo convierte en
-- percentil dentro de su propio tipo. Ver docs/EFEMERIDES.md 4.7.
-- =====================================================================================
SELECT  'hito_hr' AS tipo,
        'un hito de jonrones de por vida' AS gesta,
        'bateador' AS rol,
        'completa' AS cobertura,
        2 AS situar,
        292948 AS universo,
        -- LA PLANTILLA NO ES CONSTANTE, y ese es el truco. El contrato deja que cada fila traiga la
        -- suya, así que el detector puede añadir la frase que el motor no sabe calcular: cuántos
        -- dominicanos han llegado A ESA CIFRA. Es lo que pide docs/EFEMERIDES.md 4.7 — un hito no
        -- tiene rareza de evento, tiene rareza de NÚMERO.
        --
        -- Solo se dice cuando son cinco o menos. Con veinte no es noticia, es una lista.
        --
        -- Y SI ESE DÍA SOLO BATEÓ UNO, NO SE DICE (dueño, 2026-08-04). «Conectó su jonrón 400: ese
        -- día bateó 1 jonrón» está diciendo dos veces la misma cosa — el jonrón 400 ES ese jonrón.
        -- La coletilla solo aporta cuando hubo más de uno, porque entonces cuenta algo nuevo: que el
        -- hito cayó en un día de dos o tres. Es el caso de la mayoría, así que la plantilla se parte.
        CASE WHEN c.B_HR <= 1
             THEN 'Conectó su jonrón {magnitud} contra {rival_nombre}.'
             ELSE 'Conectó su jonrón {magnitud} contra {rival_nombre}: {detalle}.' END
            + CASE WHEN cu.cuantos <= 5
                   THEN CASE WHEN cu.cuantos = 1 THEN ' Es el único dominicano que ha llegado ahí.'
                             ELSE ' Solo ' + CAST(cu.cuantos AS varchar(2)) + ' dominicanos han llegado ahí.' END
                   ELSE '' END AS plantilla,
        c.mlb_id, c.nombre, c.fecha, c.temporada, c.game_id,
        0 AS event_id,
        c.game_type, c.equipo, c.rival, c.en_casa,
        1 AS signo,
        (c.ac_hr / 100) * 100 AS magnitud,
        c.wpa_bat AS wpa_jugador,
        c.li_max,
        'ese día bateó ' + CAST(c.B_HR AS varchar(2)) + CASE WHEN c.B_HR = 1 THEN ' jonrón' ELSE ' jonrones' END AS detalle,
        c.equipo_nombre, c.rival_nombre,
        '' AS oponente
FROM    #carrera c
-- Cuántos dominicanos DISTINTOS alcanzaron alguna vez esta misma cifra. Se agrupa por PLAYER_ID y
-- nunca por nombre: hay tres Luis Castillo y dos Nelson Cruz en el maestro (ver 3.0.1).
CROSS APPLY (SELECT COUNT(DISTINCT x.PLAYER_ID) AS cuantos
             FROM   #carrera x
             WHERE  x.ac_hr >= (c.ac_hr / 100) * 100) cu
WHERE   c.B_HR > 0
  AND   c.ac_hr / 100 > (c.ac_hr - c.B_HR) / 100;
