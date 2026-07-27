"""La auditoría de coeficientes de batazos: `manage.py check_batted_balls` (SAB-02).

Lo que se protege acá es que el comando SIRVA, que no es lo mismo que que funcione:

- Que encuentre el descuadre grande, obviamente.
- Que el ruido de una unidad no lo tumbe. Si cada corrida terminara en rojo por un batazo suelto,
  nadie volvería a correrlo y el comando dejaría de valer para lo que se construyó.
- Que **cuente** lo que tolera. Una tolerancia sin contador es una venda: se comería en silencio un
  fallo sistemático, que es justo lo que esta auditoría tiene que cazar.
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

# 60 outs + 40 hits = 100 batazos contra 100 BIP: cuadra clavado. Cada test lo descuadra a su gusto.
CUADRA: dict[str, int] = {
    "ground_outs": 30,
    "fly_outs": 20,
    "line_outs": 5,
    "pop_outs": 5,
    "ground_hits": 20,
    "fly_hits": 14,
    "line_hits": 5,
    "pop_hits": 1,
    "balls_in_play": 100,
}


def _fila(exceso: int = 0, season: int = 2015, pid: int = 400089) -> None:
    """Una fila de pitcheo que se pasa de `balls_in_play` por `exceso` batazos."""
    jugador = Player.objects.create(**_other_player(player_id=pid, dgl_id="s01", full_name="Un Lanzador"))
    campos = {**CUADRA, "pop_hits": CUADRA["pop_hits"] + exceso}
    Pitching.objects.create(player=jugador, season=season, stint=1, **campos)


@pytest.mark.django_db
def test_un_descuadre_grande_hace_fallar_el_comando(capsys: Any) -> None:
    _fila(exceso=5)
    with pytest.raises(SystemExit) as salida:
        call_command("check_batted_balls")
    assert salida.value.code == 1
    assert "5 batazo(s) por encima de 100 BIP" in capsys.readouterr().out


@pytest.mark.django_db
def test_un_batazo_de_mas_es_ruido_y_no_tumba_la_auditoria(capsys: Any) -> None:
    """El caso real que motivó la tolerancia: MLB descuadrado por uno consigo mismo."""
    _fila(exceso=1)
    call_command("check_batted_balls")  # no levanta SystemExit
    salida = capsys.readouterr().out
    assert "1 fila(s) se pasan por ≤1 batazo(s)" in salida
    assert "fuera de lo esperado" in salida


@pytest.mark.django_db
def test_lo_tolerado_se_cuenta_aunque_no_se_liste(capsys: Any) -> None:
    """Que el contador salte de 1 a 800 es la señal de un fallo sistemático.

    Sin este renglón la tolerancia sería una venda: se tragaría una carga mal armada entera, fila
    por fila, sin que nada lo dijera.
    """
    for i, pid in enumerate((100, 200, 300)):
        jugador = Player.objects.create(**_other_player(player_id=pid, dgl_id=f"x{i}", full_name=f"J{i}"))
        Pitching.objects.create(player=jugador, season=2015, stint=1, **{**CUADRA, "pop_hits": CUADRA["pop_hits"] + 1})
    call_command("check_batted_balls")
    assert "3 fila(s) se pasan por ≤1 batazo(s)" in capsys.readouterr().out


@pytest.mark.django_db
def test_con_tolerancia_cero_hasta_un_batazo_falla(capsys: Any) -> None:
    """La regla estricta sigue disponible para auditar a fondo."""
    _fila(exceso=1)
    with pytest.raises(SystemExit):
        call_command("check_batted_balls", "--tolerancia", "0")
    assert "1 batazo(s) por encima de 100 BIP" in capsys.readouterr().out


@pytest.mark.django_db
def test_una_anomalia_grande_pero_aceptada_no_tumba_la_auditoria(capsys: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """`ACEPTADAS` cubre lo que la tolerancia no puede: un descuadre grande ya investigado.

    Se inyecta con `monkeypatch` porque hoy la lista está VACÍA —la única anomalía real cae dentro
    de la tolerancia— y una prueba que dependiera de su contenido se caería al podarla.
    """
    monkeypatch.setattr(comando, "ACEPTADAS", {("pitcheo", 400089, 2015): "x" * 70})
    _fila(exceso=5)
    call_command("check_batted_balls")  # no levanta SystemExit
    assert "conocida ·" in capsys.readouterr().out


@pytest.mark.django_db
def test_avisa_de_una_excepcion_que_ya_no_hace_falta(capsys: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin fila que la dispare, la entrada de `ACEPTADAS` sobra y hay que borrarla."""
    monkeypatch.setattr(comando, "ACEPTADAS", {("pitcheo", 1, 1999): "x" * 70})
    call_command("check_batted_balls")
    assert "y ya no falla: sacala de la lista" in capsys.readouterr().out


@pytest.mark.django_db
def test_una_fila_que_cuadra_no_dice_nada(capsys: Any) -> None:
    _fila(exceso=0)
    call_command("check_batted_balls")
    salida = capsys.readouterr().out
    assert "batazo(s) por encima" not in salida
    assert "se pasan por" not in salida


def test_cada_excepcion_lleva_su_porque() -> None:
    """Añadir algo a `ACEPTADAS` es una decisión sobre los datos, no un atajo para callar el comando.

    Sin esta prueba, la lista se puede engordar con una tupla suelta y sin explicación — que es
    exactamente como una lista de excepciones deja de ser auditable.
    """
    for clave, motivo in comando.ACEPTADAS.items():
        assert len(clave) == 3, clave
        assert len(motivo) > 60, f"{clave} no explica por qué se acepta"
