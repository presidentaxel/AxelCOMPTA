"""Signature électronique d'un document — doc 18 (`workflow` : « validation,
revue, signature électronique »), doc 20 §4/§5.

**Contrat pensé pour la prod, pas juste pour la démo** (Louis, 2026-09-11 :
« on fait la démo en pensant à la prod, ne fais pas un système qu'il
faudra entièrement refaire »). `SignatureProvider` est l'abstraction que
brancheront plus tard les vrais prestataires eIDAS (Universign, Yousign/
Youtrust…, comparatif doc 20 §7) une fois ADR-004 tranché — `signer()` ne
change pas de signature de méthode entre la démo et la prod, seule
l'implémentation change (même principe que `DataProvider`, doc 13 §2, ou
que `DigifactoryProvider` chemin B → chemin A, doc 16).

**Ce que la démo ne fait jamais** : produire une vraie signature qualifiée
RGS (impossible sans certificat + prestataire réel, doc 20 §4). Le
`qualifie=False` sur `DocumentSigne` est le signal explicite qu'aucun
document signé par ce provider ne doit jamais être déposé pour de vrai —
doctrine d'erreurs doc 08 §5 : un artefact de démo ne doit jamais pouvoir
se faire passer pour un vrai document officiel.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from axelcompta.core.ids import DossierId, UserId


@dataclass(frozen=True, slots=True)
class DocumentSigne:
    """Le résultat d'une signature — `qualifie` distingue une vraie
    signature électronique qualifiée RGS (V1, prestataire à choisir,
    ADR-004) d'un tampon de démo (toujours `False` ici)."""

    contenu_pdf: bytes
    signataire: UserId
    signe_le: datetime
    provider: str  # "demo" en démo ; nom du prestataire réel en V1
    qualifie: bool


class SignatureProvider(ABC):
    """Frontière : produit un `DocumentSigne` à partir d'un PDF non signé.
    Le prestataire réel (V1) fera probablement un aller-retour réseau
    (upload, redirection ou iframe selon le prestataire, doc 20 §7) —
    cette interface n'en présume rien, `signer()` reste une opération
    unique du point de vue de l'appelant."""

    @abstractmethod
    def signer(self, contenu_pdf: bytes, signataire: UserId) -> DocumentSigne:
        """Signe `contenu_pdf` au nom de `signataire`."""


class SignatureRepository(ABC):
    """Frontière de persistance — un document signé doit survivre entre
    deux requêtes (même principe que `DecisionRepository`, doc 17 §9 bloc
    A : « pas juste un changement d'état côté React »).

    **Append-only depuis le 2026-09-11** (Louis : « je veux pouvoir prouver
    légalement que la personne a signé, donc il faut une trace
    électronique »). Écart corrigé par rapport à la version du même jour,
    plus tôt : `enregistrer` remplaçait la signature précédente
    (raisonnement d'alors : « pas besoin d'historique pour la démo ») — un
    enregistrement qu'on peut écraser n'est jamais une preuve. Même
    principe que `DecisionHumaine` (immuable, historique complet), pas une
    exception."""

    @abstractmethod
    def enregistrer(
        self, dossier_id: DossierId, type_document: str, document: DocumentSigne
    ) -> None:
        """Ajoute une signature à l'historique — ne remplace ni ne
        supprime jamais une signature existante pour ce dossier/type."""

    @abstractmethod
    def dernier(self, dossier_id: DossierId, type_document: str) -> DocumentSigne | None:
        """La signature la plus récente pour ce dossier/type, ou `None` si
        jamais signé."""

    @abstractmethod
    def lister(self, dossier_id: DossierId, type_document: str) -> tuple[DocumentSigne, ...]:
        """Tout l'historique des signatures pour ce dossier/type, triées
        par date — la preuve elle-même, jamais purgée."""

    def types_presents(
        self, dossier_ids: Sequence[DossierId], types_document: Sequence[str]
    ) -> dict[DossierId, set[str]]:
        """Pour chaque dossier, ceux des `types_document` qui ont au moins une
        signature. Un portefeuille entier d'un coup : par défaut un `dernier`
        par dossier et par type, une implémentation en base le fait en une
        requête, sans lire les PDF."""
        return {
            dossier_id: {
                type_document
                for type_document in types_document
                if self.dernier(dossier_id, type_document) is not None
            }
            for dossier_id in dossier_ids
        }
