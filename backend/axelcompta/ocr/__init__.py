"""OCR des documents d'une fiche d'import (AXE-943).

Un appel par document : le PDF (ou l'image) part à Claude, qui rend un JSON
au schéma imposé de sa catégorie. Haiku d'abord ; si un contrôle échoue,
Sonnet relit ; s'il échoue encore, le document va à un humain, avec la
raison en rouge.

Le document part en entier, sans pseudonymisation : seule exception à
l'invariant n° 5, actée par l'ADR-009 (AXE-994). Ne pas l'étendre à un autre
usage sans nouvel ADR.
"""
