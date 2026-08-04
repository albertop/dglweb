-- =====================================================================================
-- La victoria 50, 100, 150… Medido: 62 cruces, el hito mas raro.
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
SELECT  'hito_win' AS tipo,
        'un hito de victorias de por vida' AS gesta,
        'lanzador' AS rol,
        'completa' AS cobertura,
        2 AS situar,
        288826 AS universo,
        -- LA PLANTILLA NO ES CONSTANTE, y ese es el truco. El contrato deja que cada fila traiga la
        -- suya, así que el detector puede añadir la frase que el motor no sabe calcular: cuántos
        -- dominicanos han llegado A ESA CIFRA. Es lo que pide docs/EFEMERIDES.md 4.7 — un hito no
        -- tiene rareza de evento, tiene rareza de NÚMERO.
        --
        -- Solo se dice cuando son cinco o menos. Con veinte no es noticia, es una lista.
        'Llegó a {magnitud} victorias de por vida, contra {rival_nombre}: {detalle}.'
            + CASE WHEN cu.cuantos <= 5
                   THEN CASE WHEN cu.cuantos = 1 THEN ' Es el único dominicano que ha llegado ahí.'
                             ELSE ' Solo ' + CAST(cu.cuantos AS varchar(2)) + ' dominicanos han llegado ahí.' END
                   ELSE '' END AS plantilla,
        c.mlb_id, c.nombre, c.fecha, c.temporada, c.game_id,
        0 AS event_id,
        c.game_type, c.equipo, c.rival, c.en_casa,
        1 AS signo,
        (c.ac_w / 50) * 50 AS magnitud,
        c.wpa_pit AS wpa_jugador,
        c.li_max,
        -- QUÉ HIZO ESE DÍA, que es lo único que informa. Decía «la ganó él mismo», que además de no
        -- querer decir nada era redundante: si el contador de victorias subió, la ganó él.
        'ese día lanzó ' + CAST(c.P_OUT / 3 AS varchar(3)) + CASE c.P_OUT % 3 WHEN 1 THEN '.1' WHEN 2 THEN '.2' ELSE '' END + CASE WHEN c.P_OUT = 3 THEN ' entrada' ELSE ' entradas' END
            + CASE WHEN c.P_ER = 0 THEN ' sin carreras limpias'
                   WHEN c.P_ER = 1 THEN ' y permitió 1 limpia'
                   ELSE ' y permitió ' + CAST(c.P_ER AS varchar(2)) + ' limpias' END AS detalle,
        c.equipo_nombre, c.rival_nombre,
        '' AS oponente
FROM    #carrera c
-- Cuántos dominicanos DISTINTOS alcanzaron alguna vez esta misma cifra. Se agrupa por PLAYER_ID y
-- nunca por nombre: hay tres Luis Castillo y dos Nelson Cruz en el maestro (ver 3.0.1).
CROSS APPLY (SELECT COUNT(DISTINCT x.PLAYER_ID) AS cuantos
             FROM   #carrera x
             WHERE  x.ac_w >= (c.ac_w / 50) * 50) cu
WHERE   c.P_W > 0
  AND   c.ac_w / 50 > (c.ac_w - c.P_W) / 50;
