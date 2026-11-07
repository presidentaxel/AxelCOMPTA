"""AXE-841 : une seule tête Alembic, et une base en retard est refusée."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from axelcompta.core.schema import (
    PlusieursTetes,
    SchemaEnRetard,
    tete_unique,
    verifier_schema,
)


def test_les_migrations_du_depot_n_ont_qu_une_tete() -> None:
    """Échoue en CI si deux PR ont chacune ajouté une migration sur la même
    révision : le message dit laquelle rebrancher."""
    assert tete_unique()


def _migration(dossier: Path, revision: str, parent: str | None) -> None:
    (dossier / f"{revision}_m.py").write_text(
        f'revision = "{revision}"\ndown_revision = {parent!r}\n'
        "branch_labels = None\ndepends_on = None\n"
        "def upgrade():\n    pass\ndef downgrade():\n    pass\n"
    )


def test_deux_migrations_sur_la_meme_revision_sont_signalees(tmp_path: Path) -> None:
    (tmp_path / "versions").mkdir()
    (tmp_path / "script.py.mako").write_text("")
    _migration(tmp_path / "versions", "a1", None)
    _migration(tmp_path / "versions", "b2", "a1")
    _migration(tmp_path / "versions", "c3", "a1")

    with pytest.raises(PlusieursTetes, match=r"b2 \(part de a1\).*c3 \(part de a1\)"):
        tete_unique(tmp_path)


@pytest.mark.parametrize(("en_base", "attendu"), [("a1", "a1"), (None, "a1"), ("a0", "a1")])
def test_verifier_schema(en_base: str | None, attendu: str) -> None:
    with patch("axelcompta.core.schema.revision_en_base", return_value=en_base):
        if en_base == attendu:
            verifier_schema(object(), attendu)  # type: ignore[arg-type]
        else:
            with pytest.raises(SchemaEnRetard, match="alembic upgrade head"):
                verifier_schema(object(), attendu)  # type: ignore[arg-type]
