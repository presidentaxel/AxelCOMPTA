import type { SelectOption } from "@/components/ui/select";
import { ETAPES_FRISE } from "@/lib/filtres-portefeuille";
import { libelleTag, SANS_TAG, TOUS_LES_TAGS } from "@/lib/tags";
import { libelleTvaRecettes } from "@/lib/dossier-libelles";
import type { ReglageTags } from "@/lib/types";

/** Valeur du filtre « Comptes bancaires » qui garde les entreprises dont le
 * dirigeant n'a pas encore choisi ses comptes. */
export const COMPTES_A_CHOISIR = "a_choisir";

export type FiltreCompte = "tous" | "sans_compte" | "invite" | "ouvert";
export type FiltreResultat = "tous" | "negatif" | "positif";
export type Tri = "nom" | "etape" | "resultat";

/** Les filtres et le tri tels que l'URL les porte (`?compte=…&tri=…`). Le
 * format de l'URL n'a pas changé avec la refonte : les liens existants
 * continuent de marcher. */
export type EtatFiltres = {
  recherche: string;
  compte: FiltreCompte;
  resultat: FiltreResultat;
  forme: string;
  tva: string;
  etape: string;
  banque: string;
  tag: string;
  tri: Tri;
};

export function lireCompte(valeur: string | null): FiltreCompte {
  if (valeur === "sans_compte" || valeur === "invite" || valeur === "ouvert") return valeur;
  return "tous";
}

export function lireResultat(valeur: string | null): FiltreResultat {
  if (valeur === "positif" || valeur === "negatif") return valeur;
  return "tous";
}

export function lireTri(valeur: string | null): Tri {
  if (valeur === "etape" || valeur === "resultat") return valeur;
  return "nom";
}

/** Nombre de filtres posés, sans la recherche (qui a son champ, toujours
 * visible) : c'est le nombre que porte le bouton « Filtres », et il ouvre
 * le panneau au chargement pour que l'état de l'URL ne soit jamais caché. */
export function nombreDeFiltres(etat: EtatFiltres): number {
  return [
    etat.compte !== "tous",
    etat.resultat !== "tous",
    etat.forme !== "toutes",
    etat.tva !== "toutes",
    etat.etape !== "toutes",
    etat.banque !== "toutes",
    etat.tag !== TOUS_LES_TAGS,
    etat.tri !== "nom",
  ].filter(Boolean).length;
}

const LIBELLES_COMPTE: Record<FiltreCompte, string> = {
  tous: "Tous",
  sans_compte: "Sans compte",
  invite: "Invitation envoyée",
  ouvert: "Compte ouvert",
};

const LIBELLES_RESULTAT: Record<FiltreResultat, string> = {
  tous: "Tous",
  positif: "Positif",
  negatif: "Négatif",
};

export const LIBELLES_TRI: Record<Tri, string> = {
  nom: "Nom",
  etape: "Étape bloquante",
  resultat: "Résultat",
};

/** Radix interdit une option de valeur `""` : « Tous » porte donc une vraie
 * valeur (`tous`, `toutes`), les mêmes que l'URL. Une forme ou un régime vide
 * côté API est écarté : il ferait planter la liste. */
function sansVide(valeurs: string[]): string[] {
  return valeurs.filter((valeur) => valeur !== "");
}

export function optionsCompte(): SelectOption[] {
  return (Object.keys(LIBELLES_COMPTE) as FiltreCompte[]).map((value) => ({
    value,
    label: LIBELLES_COMPTE[value],
  }));
}

export function optionsResultat(): SelectOption[] {
  return (["tous", "positif", "negatif"] as FiltreResultat[]).map((value) => ({
    value,
    label: LIBELLES_RESULTAT[value],
  }));
}

export function optionsForme(formes: string[]): SelectOption[] {
  return [
    { value: "toutes", label: "Toutes" },
    ...sansVide(formes).map((value) => ({ value, label: value })),
  ];
}

export function optionsTva(regimes: string[]): SelectOption[] {
  return [
    { value: "toutes", label: "Toutes" },
    ...sansVide(regimes).map((value) => ({ value, label: libelleTvaRecettes(value) })),
  ];
}

export function optionsEtape(): SelectOption[] {
  return [
    { value: "toutes", label: "Toutes" },
    ...ETAPES_FRISE.map((value) => ({ value, label: value })),
  ];
}

export function optionsBanque(): SelectOption[] {
  return [
    { value: "toutes", label: "Tous" },
    { value: COMPTES_A_CHOISIR, label: "À choisir" },
  ];
}

export function optionsTag(reglage: ReglageTags): SelectOption[] {
  return [
    { value: TOUS_LES_TAGS, label: "Tous" },
    { value: SANS_TAG, label: "Sans tag" },
    ...reglage.tags
      .filter((option) => option.nom !== "")
      .map((option) => ({ value: option.nom, label: libelleTag(option.nom) })),
  ];
}

export function optionsTri(): SelectOption[] {
  return (Object.keys(LIBELLES_TRI) as Tri[]).map((value) => ({ value, label: LIBELLES_TRI[value] }));
}
