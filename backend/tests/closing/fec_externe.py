"""Un FEC « d'un autre outil » pour les tests d'AXE-804 : exercice 2025 d'une
SASU (capital, ventes, carburant, emprunt, TVA), numéros par journal."""

from __future__ import annotations

ENTETE = (
    "JournalCode",
    "JournalLib",
    "EcritureNum",
    "EcritureDate",
    "CompteNum",
    "CompteLib",
    "CompAuxNum",
    "CompAuxLib",
    "PieceRef",
    "PieceDate",
    "EcritureLib",
    "Debit",
    "Credit",
    "EcritureLet",
    "DateLet",
    "ValidDate",
    "Montantdevise",
    "Idevise",
)
SIREN = "987142031"
NOM = f"{SIREN}FEC20251231.txt"

# (journal, numéro, date, compte, débit, crédit)
ECRITURES: list[tuple[str, str, str, str, str, str]] = [
    ("OD", "OD0001", "20250102", "51200000", "1000,00", "0,00"),
    ("OD", "OD0001", "20250102", "10100000", "0,00", "1000,00"),
    ("BQ", "BQ0001", "20250301", "51200000", "8000,00", "0,00"),
    ("BQ", "BQ0001", "20250301", "16400000", "0,00", "8000,00"),
    ("VE", "VE0001", "20250630", "51200000", "55000,00", "0,00"),
    ("VE", "VE0001", "20250630", "70600000", "0,00", "50000,00"),
    ("VE", "VE0001", "20250630", "44571000", "0,00", "5000,00"),
    ("AC", "AC0001", "20250915", "60610000", "20000,00", "0,00"),
    ("AC", "AC0001", "20250915", "51200000", "0,00", "20000,00"),
]


def fec(
    lignes: list[tuple[str, str, str, str, str, str]] | None = None,
    separateur: str = "\t",
    valid: str = "20260115",
    fin: str = "\r\n",
) -> str:
    sortie = [separateur.join(ENTETE)]
    for journal, numero, date, compte, debit, credit in lignes or ECRITURES:
        zones = [journal, journal, numero, date, compte, "Libellé", "", "", "P1", date, "Ligne"]
        zones += [debit, credit, "", "", valid, "", ""]
        sortie.append(separateur.join(zones))
    return fin.join(sortie) + fin
