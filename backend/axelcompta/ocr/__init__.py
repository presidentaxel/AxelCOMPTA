"""OCR des documents d'une fiche d'import (AXE-943).

Un appel par document : le PDF (ou l'image) part à Claude, qui rend un JSON
au schéma imposé de sa catégorie. Haiku d'abord ; si un contrôle échoue,
Sonnet relit ; s'il échoue encore, le document va à un humain, avec la
raison en rouge.
"""
