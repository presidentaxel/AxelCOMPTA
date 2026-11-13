def test_le_registre_en_memoire_refuse_doublon_et_double_cession() -> None:
    """AXE-802 : le registre est en ajout seul."""
    from datetime import date

    import pytest

    from axelcompta.closing.immobilisations import Cession, Immobilisation
    from axelcompta.core.ids import DossierId, TenantId
    from axelcompta.tenants.provisions_cloture import (
        ImmobilisationConnue,
        InMemoryProvisionsClotureRepository,
    )

    depot = InMemoryProvisionsClotureRepository()
    t, d = TenantId("t"), DossierId("d")
    fiche = Immobilisation("v1", "Toyota", "2182", date(2026, 4, 1), 30_000_00, 60)
    depot.ajouter_immobilisation(t, d, fiche)
    with pytest.raises(ImmobilisationConnue):
        depot.ajouter_immobilisation(t, d, fiche)
    depot.enregistrer_cession(t, d, "v1", Cession(date(2028, 6, 30), 1))
    with pytest.raises(ImmobilisationConnue):
        depot.enregistrer_cession(t, d, "v1", Cession(date(2028, 6, 30), 1))
    assert depot.lister_immobilisations(t, d)[0].cession is not None
