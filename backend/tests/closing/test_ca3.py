from axelcompta.closing.ca3 import declaration_ca3


def test_tva_a_payer_quand_la_collectee_depasse_la_deductible() -> None:
    # Soldes débiteur positif : 44571 créditeur, 44566 débiteur.
    ca3 = declaration_ca3({"44571": -10_000, "44566": 2_000, "512": 8_000})
    assert ca3 == {"COLLECTEE": 10_000, "DEDUCTIBLE": 2_000, "DUE": 8_000}


def test_credit_de_tva_est_une_due_negative() -> None:
    ca3 = declaration_ca3({"44571": -1_000, "44566": 4_000})
    assert ca3["DUE"] == -3_000
