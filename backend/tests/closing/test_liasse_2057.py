from axelcompta.closing.liasse_2057 import echeances_2057


def test_tout_a_un_an_au_plus_sauf_les_emprunts() -> None:
    balance = {
        "411000": 1_200_00,  # client
        "44566": 300_40,  # TVA déductible
        "486": 100_00,  # charge constatée d'avance
        "401000": -800_00,  # fournisseur
        "44571": -500_00,  # TVA collectée
        "164000": -9_000_00,  # emprunt bancaire
        "512100": -50_00,  # découvert
        "512200": 2_000_00,  # banque débitrice : pas au 2057
        "101": -1_000_00,  # capital : pas au 2057
    }
    cases = echeances_2057(balance)
    assert cases["UX"] == cases["UX.1AN"] == 1_200
    assert cases["VB"] == 300
    assert cases["VS"] == 100
    assert cases["VT"] == cases["VU"] == 1_600
    assert cases["8B"] == cases["8B.1AN"] == 800
    assert cases["VW"] == 500
    assert cases["VG"] == cases["VG.1AN"] == 50
    assert cases["VH"] == 9_000 and "VH.1AN" not in cases  # échéance à saisir
    assert cases["VY"] == 10_350
    assert cases["VZ"] == 1_350


def test_creance_immobilisee_dans_sa_colonne_codee() -> None:
    cases = echeances_2057({"275": 500_00})
    assert cases["UT"] == cases["UV"] == 500
    assert "UT.1AN" not in cases
