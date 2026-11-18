"""AXE-987 : les récapitulatifs mensuels Uber se lisent sans OCR."""

from __future__ import annotations

from axelcompta.ingestion.recaps_plateforme import lire_recap, plateforme_du_nom

# Textes synthétiques, à la forme des deux formats vus (société fictive).
ANCIEN = """Uber B.V.
Burgerweeshuispad 301,
Récapitulatif fiscal de la période 2025/9
EXEMPLE SAS
Nº SIREN :   123456789
TARIFICATION
DÉTAIL DES AUTRES REVENUS
Prix de la course (frais de service Uber inclus)
1
€1,000.00
Péages
€20.00
Total
€1,020.00
Total des revenus nets (hors frais de service et TVA)
€800.00
Divers
€70.00
Parrainages / Primes
€10.00
Total
€80.00
Frais de service pour les courses Uber
€300.00
"""

NOUVEAU = """Uber B.V.
SIREN/SIRET: 123456789
01-30 Novembre 2025
Récapitulatif fiscal
Revenus issus de courses
5
 
000,00 €
0,00 €
Revenus issus d'autres services
100,50 €
100,50 €
Frais de service Uber
1
 
500,25 €
0,00 €
Montant total
3
 
600,25 €
"""


def test_l_ancien_format_est_lu_et_tombe_juste() -> None:
    recap = lire_recap(ANCIEN)
    assert recap is not None
    assert (recap.plateforme, recap.mois, recap.siren) == ("uber", "2025-09", "123456789")
    assert (recap.courses_cts, recap.autres_cts, recap.frais_cts, recap.net_cts) == (
        102_000,
        8_000,
        30_000,
        80_000,
    )
    assert recap.juste


def test_le_nouveau_format_aux_montants_coupes_est_lu() -> None:
    recap = lire_recap(NOUVEAU)
    assert recap is not None
    assert (recap.mois, recap.courses_cts, recap.autres_cts) == ("2025-11", 500_000, 10_050)
    assert (recap.frais_cts, recap.net_cts, recap.juste) == (150_025, 360_025, True)


def test_un_montant_faux_se_voit() -> None:
    recap = lire_recap(NOUVEAU.replace("100,50 €\n100,50 €", "100,00 €\n100,00 €"))
    assert recap is not None and not recap.juste


def test_un_autre_document_n_est_pas_un_recapitulatif() -> None:
    assert lire_recap("Relevé de compte Bred\nSolde au 30/09") is None


def test_la_plateforme_se_lit_dans_le_nom() -> None:
    assert plateforme_du_nom("uber_monthly_2025_9.pdf") == "uber"
    assert plateforme_du_nom("Bolt - octobre.pdf") == "bolt"
    assert plateforme_du_nom("releve.pdf") is None
