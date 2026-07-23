"""The qualifier formula grammar, in one place so both the models and the engine can use it.

A qualifier is a simple `FIELD OP NUMBER` comparison (e.g. `PA>=502`). It lives here, apart from
`qualifier.py` (which imports the models), so the models can validate their fields without a cycle.
"""

import re

from django.core.exceptions import ValidationError

QUALIFIER_RE = re.compile(r"^\s*([A-Za-z_]+)\s*(>=|<=|>|<|=)\s*(\d+(?:\.\d+)?)\s*$")


def validate_qualifier_formula(value: str) -> None:
    """Model/form validator: a non-blank qualifier must parse as `FIELD OP NUMBER` (e.g. `PA>=502`)."""
    if value and QUALIFIER_RE.match(value) is None:
        raise ValidationError("Fórmula de umbral inválida. Usá algo como 'PA>=502' (campo, operador, número).")
