"""Couverture bancaire d'une fiche d'import (AXE-973). Pur.

Une banque est complète sur une période quand le solde le prouve :

    solde au début + somme des opérations de la période = solde à la fin,
    au centime près.

Les dates seules ne disent pas si deux jours sans opération sont un compte
calme ou un relevé perdu ; le solde, si. Entre deux soldes connus :

- **complet** : l'écart est nul ; les jours sans données sont alors des
  jours sans mouvement (le compte n'était pas encore ouvert, ou calme) ;
- **écart** : des données couvrent la période, mais il manque N € (une
  opération perdue, un relevé incomplet) ; les indices aident à situer le
  trou (silence anormal, opération mensuelle absente) ;
- **manquant** : aucune source ne couvre ces jours, et soit le solde ne
  tombe pas juste, soit aucun solde ne permet de le savoir ;
- **couvert** : des données couvrent ces jours, mais aucun solde connu ne
  permet de le prouver (avant le premier solde, après le dernier).

Les sources d'opérations (FEC, QIF, Digifactory…) se recouvrent : une même
opération (même jour, même montant) n'est comptée qu'une fois, en prenant
le plus grand nombre d'occurrences vu dans une seule source.

Les soldes connus (« ancres ») sont le solde **en fin de journée** : clôture
d'un FEC, à-nouveaux de l'exercice suivant, solde Digifactory, solde lu sur
un relevé, 0 € la veille de la création de la société.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

EtatPeriode = Literal["complet", "ecart", "manquant", "couvert"]
UN_JOUR = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class SourceOperations:
    """Les opérations d'un compte lues dans une source, et les jours qu'elle
    couvre (un relevé couvre aussi ses jours sans opération)."""

    compte: str
    source: str  # « FEC 2024 », « QIF qonto.qif », « Digifactory »
    debut: date
    fin: date
    operations: tuple[tuple[date, int], ...] = ()


@dataclass(frozen=True, slots=True)
class Solde:
    """Le solde d'un compte en fin de journée."""

    compte: str
    le: date
    cts: int
    source: str


@dataclass(frozen=True, slots=True)
class Periode:
    debut: date
    fin: date
    etat: EtatPeriode
    sources: tuple[str, ...] = ()
    ecart_cts: int | None = None  # solde attendu − solde calculé, si connu
    indices: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Couverture:
    compte: str
    periodes: tuple[Periode, ...]
    soldes: tuple[Solde, ...] = field(default=())
    incoherences: tuple[str, ...] = ()  # deux soldes différents le même jour

    @property
    def a_completer(self) -> tuple[Periode, ...]:
        return tuple(p for p in self.periodes if p.etat in ("manquant", "ecart"))


def _fusion(sources: Sequence[SourceOperations]) -> Counter[tuple[date, int]]:
    """Les opérations sans doublon d'une source à l'autre."""
    union: Counter[tuple[date, int]] = Counter()
    for source in sources:
        union |= Counter(source.operations)
    return union


def _jours_couverts(sources: Sequence[SourceOperations]) -> list[tuple[date, date]]:
    """Les intervalles couverts par au moins une source, fusionnés."""
    intervalles = sorted((s.debut, s.fin) for s in sources)
    fusionnes: list[tuple[date, date]] = []
    for debut, fin in intervalles:
        if fusionnes and debut <= fusionnes[-1][1] + UN_JOUR:
            fusionnes[-1] = (fusionnes[-1][0], max(fusionnes[-1][1], fin))
        else:
            fusionnes.append((debut, fin))
    return fusionnes


def _decouper(
    debut: date, fin: date, couverts: list[tuple[date, date]]
) -> list[tuple[date, date, bool]]:
    """[debut, fin] découpé en morceaux couverts ou non."""
    morceaux: list[tuple[date, date, bool]] = []
    curseur = debut
    for c_debut, c_fin in couverts:
        if c_fin < curseur or c_debut > fin:
            continue
        if c_debut > curseur:
            morceaux.append((curseur, c_debut - UN_JOUR, False))
        haut = min(c_fin, fin)
        morceaux.append((max(c_debut, curseur), haut, True))
        curseur = haut + UN_JOUR
        if curseur > fin:
            break
    if curseur <= fin:
        morceaux.append((curseur, fin, False))
    return morceaux


def _sources_de(debut: date, fin: date, sources: Sequence[SourceOperations]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(s.source for s in sources if s.debut <= fin and s.fin >= debut))


def _indices(
    debut: date, fin: date, operations: Counter[tuple[date, int]], rythme: int
) -> tuple[str, ...]:
    """Où chercher le trou d'une période en écart : le silence le plus long,
    s'il dépasse nettement le rythme habituel du compte, et les mois sans
    opération."""
    jours = sorted({j for j, _ in operations if debut <= j <= fin})
    bornes = [debut - UN_JOUR, *jours, fin + UN_JOUR]
    silences = [(b - a).days - 1 for a, b in zip(bornes, bornes[1:], strict=False)]
    indices = []
    if silences:
        plus_long = max(silences)
        i = silences.index(plus_long)
        if plus_long > max(2 * rythme, 7):
            du, au = bornes[i] + UN_JOUR, bornes[i + 1] - UN_JOUR
            indices.append(
                f"Aucune opération du {du:%d/%m/%Y} au {au:%d/%m/%Y} ({plus_long} jours)."
            )
    mois = sorted({(j.year, j.month) for j in jours})
    tous, curseur = [], date(debut.year, debut.month, 1)
    while curseur <= fin:
        tous.append((curseur.year, curseur.month))
        curseur = date(curseur.year + curseur.month // 12, curseur.month % 12 + 1, 1)
    vides = [f"{m:02d}/{a}" for a, m in tous if (a, m) not in mois]
    if vides and len(vides) < len(tous):
        indices.append("Mois sans opération : " + ", ".join(vides) + ".")
    return tuple(indices)


def _rythme(operations: Counter[tuple[date, int]]) -> int:
    """Le silence habituel du compte : la médiane des écarts entre deux jours
    d'opération."""
    jours = sorted({j for j, _ in operations})
    ecarts = sorted((b - a).days for a, b in zip(jours, jours[1:], strict=False))
    return ecarts[len(ecarts) // 2] if ecarts else 7


def _ancres(soldes: Iterable[Solde]) -> tuple[list[Solde], list[str]]:
    """Un solde par jour ; deux soldes différents le même jour sont signalés
    et le premier reçu est gardé."""
    par_jour: dict[date, Solde] = {}
    incoherences = []
    for solde in sorted(soldes, key=lambda s: s.le):
        deja = par_jour.get(solde.le)
        if deja is None:
            par_jour[solde.le] = solde
        elif deja.cts != solde.cts:
            incoherences.append(
                f"Le {solde.le:%d/%m/%Y} : {deja.source} dit {_euros(deja.cts)}, "
                f"{solde.source} dit {_euros(solde.cts)}."
            )
    return [par_jour[j] for j in sorted(par_jour)], incoherences


def couverture(
    compte: str,
    sources: Sequence[SourceOperations],
    soldes: Sequence[Solde],
    debut: date,
    fin: date,
) -> Couverture:
    """La couverture d'un compte du `debut` à la `fin` (inclus)."""
    sources = [s for s in sources if s.compte == compte]
    ancres, incoherences = _ancres(s for s in soldes if s.compte == compte)
    operations = _fusion(sources)
    couverts = _jours_couverts(sources)
    rythme = _rythme(operations)
    dans = [a for a in ancres if debut - UN_JOUR <= a.le <= fin]
    # Les segments : du début à la première ancre, entre deux ancres, de la
    # dernière ancre à la fin. Une ancre est un solde en fin de journée : le
    # segment qui la suit commence le lendemain.
    coupures = [debut - UN_JOUR, *[a.le for a in dans], fin]
    coupures = sorted(set(coupures))
    par_jour = {a.le: a for a in dans}
    periodes: list[Periode] = []
    for gauche, droite in zip(coupures, coupures[1:], strict=False):
        s_debut, s_fin = gauche + UN_JOUR, droite
        morceaux = _decouper(s_debut, s_fin, couverts)
        ancre_debut, ancre_fin = par_jour.get(gauche), par_jour.get(droite)
        if ancre_debut is None or ancre_fin is None:
            periodes += [
                Periode(d, f, "couvert" if ok else "manquant", _sources_de(d, f, sources))
                for d, f, ok in morceaux
            ]
            continue
        somme = sum(m * n for (j, m), n in operations.items() if s_debut <= j <= s_fin)
        ecart = ancre_fin.cts - ancre_debut.cts - somme
        if ecart == 0:
            # Le solde tombe juste : les jours sans données sont des jours
            # sans mouvement, la période est prouvée.
            periodes.append(
                Periode(s_debut, s_fin, "complet", _sources_de(s_debut, s_fin, sources), 0)
            )
            continue
        periodes += _segment_en_ecart(morceaux, ecart, operations, rythme, sources)
    return Couverture(compte, tuple(_fusionner(periodes)), tuple(ancres), tuple(incoherences))


def _segment_en_ecart(
    morceaux: list[tuple[date, date, bool]],
    ecart: int,
    operations: Counter[tuple[date, int]],
    rythme: int,
    sources: Sequence[SourceOperations],
) -> list[Periode]:
    """Un segment dont le solde ne tombe pas juste. S'il a des jours sans
    données, l'écart est porté par le premier trou, où chercher d'abord, et
    les jours couverts autour restent « couvert ». Sans trou, ce sont les
    jours couverts qui sont en écart, avec des indices."""
    trous = [(d, f) for d, f, ok in morceaux if not ok]
    periodes: list[Periode] = []
    for d, f, ok in morceaux:
        if not ok:
            periodes.append(Periode(d, f, "manquant", (), ecart if (d, f) == trous[0] else None))
        elif trous:
            periodes.append(Periode(d, f, "couvert", _sources_de(d, f, sources)))
        else:
            periodes.append(
                Periode(
                    d,
                    f,
                    "ecart",
                    _sources_de(d, f, sources),
                    ecart,
                    _indices(d, f, operations, rythme),
                )
            )
    return periodes


def _fusionner(periodes: list[Periode]) -> list[Periode]:
    """Deux périodes voisines au même état, sans écart chiffré, n'en font
    qu'une à l'écran."""
    fusion: list[Periode] = []
    for p in periodes:
        avant = fusion[-1] if fusion else None
        if (
            avant
            and avant.etat == p.etat
            and avant.fin + UN_JOUR == p.debut
            and avant.ecart_cts in (None, 0)
            and p.ecart_cts in (None, 0)
            and not avant.indices
            and not p.indices
        ):
            sources = tuple(dict.fromkeys((*avant.sources, *p.sources)))
            ecart = 0 if avant.ecart_cts == 0 and p.ecart_cts == 0 else None
            fusion[-1] = Periode(avant.debut, p.fin, p.etat, sources, ecart)
        else:
            fusion.append(p)
    return fusion


def correspondance(
    operations: Sequence[tuple[date, int]], autres: Sequence[tuple[date, int]]
) -> float:
    """La part des opérations de `operations` retrouvées (même jour, même
    montant) dans `autres` : un relevé QIF sans nom de compte se rattache au
    compte d'un FEC qu'il recoupe."""
    if not operations:
        return 0.0
    communes = Counter(operations) & Counter(autres)
    return sum(communes.values()) / len(operations)


def _euros(centimes: int) -> str:
    signe = "−" if centimes < 0 else ""
    return f"{signe}{abs(centimes) / 100:,.2f} €".replace(",", " ").replace(".", ",")


def phrase(periode: Periode) -> str:
    """Une période en une phrase, pour l'écran et la carte des relevés."""
    du = f"du {periode.debut:%d/%m/%Y} au {periode.fin:%d/%m/%Y}"
    if periode.etat == "complet":
        return f"Complet {du} : le solde le prouve."
    if periode.etat == "couvert":
        return f"Données {du}, sans solde pour le prouver."
    if periode.etat == "manquant":
        ecart = f" (il manque {_euros(periode.ecart_cts)} au solde)" if periode.ecart_cts else ""
        return f"Il manque les relevés {du}{ecart}."
    return f"Écart de {_euros(periode.ecart_cts or 0)} {du} : des opérations manquent."
