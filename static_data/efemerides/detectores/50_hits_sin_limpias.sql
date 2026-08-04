-- =====================================================================================
-- OCHO O MÁS HITS Y NI UNA CARRERA LIMPIA. Medido: 40 salidas, 25 lanzadores.
--
-- La gesta del que se pasa la tarde con hombres en base y no deja anotar a nadie. No es dominio —el
-- dominio ya lo cuentan `34_cg_dominante` y `33_cg_1hit`— es AGUANTE: cada entrada empieza mal y cada
-- entrada termina en cero.
--
-- EL UMBRAL, medido sobre las salidas dominicanas de 5+ entradas sin carreras limpias:
--
--     8 hits    29 salidas, 19 lanzadores   <- el corte
--     9          8, 7
--    10          3, 3                       <- el récord
--
-- Se corta en 8 porque ahí empieza a ser una rareza de verdad. Por debajo la lista se llena de
-- salidas corrientes: permitir seis o siete hits sin carreras limpias es una buena tarde de cualquier
-- abridor.
--
-- EL PISO DE CINCO ENTRADAS no es adorno. Sin él entrarían relevistas de un tercio de entrada con dos
-- hits y cero limpias, que no es la gesta: la gesta es sostenerlo durante todo el juego.
--
-- EL RÉCORD Y LO QUE CUENTA: **Joaquín Andújar, 26 de junio de 1976 — diez hits, nueve entradas y
-- CERO CARRERAS**, ni limpias ni sucias. Una blanqueada de diez hits. Le siguen Ramón Ortiz (2005) y
-- Robinson Tejeda (2006), los dos con diez. Y **Bartolo Colón aparece dos veces** con nueve, en 2013
-- y en 2015.
--
-- OJO: «sin carreras LIMPIAS» no es «sin carreras». Varias de estas salidas permitieron carreras
-- sucias por errores detrás. El texto lo distingue — dice «blanqueada» solo cuando de verdad no anotó
-- nadie.
--
-- CONVIVE CON `32_blanqueada` y `34_cg_dominante`: son la misma tarde vista por ejes distintos, y la
-- fusión (sección 7) se queda con la más rara cuando coinciden.
--
-- GRANO: juego-jugador (292.948).
-- =====================================================================================
SELECT  'hits_sin_limpias' AS tipo,
        '8+ hits permitidos sin una carrera limpia' AS gesta,
        'lanzador'                                AS rol,
        'completa'                                AS cobertura,
        288826                                    AS universo,
        1                                         AS situar,
        -- EL RIVAL VA PEGADO A LOS HITS, no al final. Con la forma anterior —«Le dieron {detalle}
        -- contra {rival_nombre}»— la coletilla de las carreras sucias se metía en medio y salía «10
        -- hits y no le anotaron una carrera limpia en 9 entradas — no le anotaron del todo contra
        -- Cincinnati Reds», que se lee a tropezones. El número entra en la plantilla porque la
        -- plantilla se declara por fila, no una vez por detector.
        'Le dieron ' + CAST(j.P_H AS varchar(2))
            + ' hits contra {rival_nombre} y no le anotaron una carrera limpia: {detalle}.' AS plantilla,
        j.mlb_id, j.nombre, j.fecha, j.temporada, j.game_id,
        0                                         AS event_id,
        j.game_type, j.equipo, j.rival, j.en_casa,
        1                                         AS signo,
        -- Los hits mandan; los outs desempatan, porque aguantar diez hits en nueve entradas pesa más
        -- que aguantarlos en cinco.
        (j.P_H * 100) + j.P_OUT                   AS magnitud,
        NULL                                      AS wpa_jugador,
        j.li_max,
        CAST(j.P_OUT / 3 AS varchar(2)) + ' entradas'
            + CASE WHEN j.P_R = 0 THEN ' sin que le anotaran del todo'
                   WHEN j.P_R = 1 THEN ', y la única carrera que le hicieron fue sucia'
                   ELSE ', y las ' + CAST(j.P_R AS varchar(2)) + ' carreras que le hicieron fueron sucias' END AS detalle,
        j.equipo_nombre, j.rival_nombre,
        ''                                        AS oponente
FROM    #juegos j
WHERE   j.P_ER = 0
  AND   j.P_OUT >= 15
  AND   j.P_H >= 8;

-- =====================================================================================
-- LA LISTA — «¿quiénes aguantaron 8+ hits sin permitir una carrera limpia?»
-- =====================================================================================
/*
SELECT  m.nameList AS lanzador, CAST(r.GAME_DT AS date) AS fecha,
        r.P_H AS hits, r.P_OUT / 3.0 AS entradas, r.P_R AS carreras, r.P_SO AS ponches
FROM    dbo.retroDailyReg r
INNER JOIN dbo.dglMaster m ON m.retroID = r.PLAYER_ID
WHERE   r.P_ER = 0 AND r.P_OUT >= 15 AND r.P_H >= 8
ORDER BY r.P_H DESC, fecha;
*/
