"""Détection d'anomalies (doc 05 §6).

Le module signale des incohérences. Un humain les qualifie. Aucun libellé
n'emploie de qualification juridique.
"""

from .service import analyser

__all__ = ["analyser"]
