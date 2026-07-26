"""Carga de datos de apoyo por CSV (Fase 4e). Ver `docs/DATOS_DE_APOYO.md`."""

from dglweb.stats.staticdata import loaders  # noqa: F401 — importar registra los loaders
from dglweb.stats.staticdata.engine import REGISTRY, Comparison, Loader, Problem, apply, compare, read, validate

__all__ = ["REGISTRY", "Comparison", "Loader", "Problem", "apply", "compare", "read", "validate"]
