"""La auditoría de coeficientes de batazos: `manage.py check_batted_balls` (SAB-02).

Lo que se protege acá es que el comando SIRVA, que no es lo mismo que que funcione:

- Que encuentre la fila imposible, obviamente.
- Que una anomalía ya decidida NO lo tumbe. Si cada corrida terminara en rojo por la fila de Soriano
  —dato de la fuente, aceptado a conciencia—, nadie volvería a correrlo y el comando dejaría de
  valer para lo que se construyó.
- Que avise cuando una entrada de `ACEPTADAS` deja de disparar. Una lista de excepciones que crece y
  nunca se poda acaba tapando problemas nuevos con el nombre de problemas viejos.
"""

from typing import Any

import pytest
from django.core.management import call_command

from dglweb.players.models import Player
from dglweb.stats.management.commands import check_batted_balls as comando
from dglweb.stats.models import Pitching
from tests.test_players import _other_player

# 60 outs + 41 hits = 101 batazos contra 100 BIP: los coeficientes sumarían 101%.
IMPOSIBLE: dict[str, int] = {
    "ground_outs": 30,
    "fly_outs": 20,
    "line_outs": 5,
    "pop_outs": 5,
    "ground_hits": 20,
    "fly_hits": 15,
    "line_hits": 5,
    "pop_hits": 1,
    "balls_in_play": 100,
}


def _fila(season: int = 2010, pid: int = 400089) -> None:
    jugador = Player.objects.create(**_other_player(player_id=pid, dgl_id="s01", full_name="Un Lanzador"))
    Pitching.objects.create(player=jugador, season=season, stint=1, **IMPOSIBLE)


@pytest.mark.django_db
def test_una_fila_imposible_hace_fallar_el_comando(capsys: Any) -> None:
    _fila(season=2015)  # una temporada que NO está en ACEPTADAS
    with pytest.raises(SystemExit) as salida:
        call_command("check_batted_balls")
    assert salida.value.code == 1
    assert "1 batazo(s) por encima de 100 BIP" in capsys.readouterr().out


@pytest.mark.django_db
def test_una_anomalia_aceptada_no_tumba_la_auditoria(capsys: Any) -> None:
    """La razón de ser de `ACEPTADAS`: que la corrida pueda salir en verde.

    Un comando que siempre termina en rojo es un comando que nadie corre.
    """
    _fila()  # ("pitcheo", 400089, 2010), que sí está en ACEPTADAS
    call_command("check_batted_balls")  # no levanta SystemExit
    salida = capsys.readouterr().out
    assert "conocida ·" in salida
    assert "fuera de lo conocido" in salida


@pytest.mark.django_db
def test_avisa_de_una_excepcion_que_ya_no_hace_falta(capsys: Any) -> None:
    """Sin fila que la dispare, la entrada de `ACEPTADAS` sobra y hay que borrarla."""
    call_command("check_batted_balls")
    assert "y ya no falla: sacala de la lista" in capsys.readouterr().out


@pytest.mark.django_db
def test_una_fila_que_cuadra_no_dice_nada(capsys: Any) -> None:
    jugador = Player.objects.create(**_other_player(player_id=1, dgl_id="b01", full_name="Otro"))
    Pitching.objects.create(player=jugador, season=2015, stint=1, **{**IMPOSIBLE, "pop_hits": 0})
    call_command("check_batted_balls")
    assert "1 batazo(s)" not in capsys.readouterr().out


def test_cada_excepcion_lleva_su_porque() -> None:
    """Añadir algo a `ACEPTADAS` es una decisión sobre los datos, no un atajo para callar el comando.

    Sin esta prueba, la lista se puede engordar con una tupla suelta y sin explicación — que es
    exactamente como una lista de excepciones deja de ser auditable.
    """
    for clave, motivo in comando.ACEPTADAS.items():
        assert len(clave) == 3, clave
        assert len(motivo) > 60, f"{clave} no explica por qué se acepta"
