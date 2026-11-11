import { formatDate } from "./format";
import { libelleMoyenPaiement } from "./moyens-paiement";
import type { AlerteAnomalie, EvenementAnomalie } from "./types";

export type EtatAlerte = AlerteAnomalie["etat"];

/** Vocabulaire de l'instruction (doc 11 §3.2) : jamais de qualification
 * juridique, seulement l'état du dossier d'instruction. */
export const LIBELLE_ETAT: Record<EtatAlerte, string> = {
  ouverte: "Ouverte",
  en_instruction: "En instruction",
  justifiee: "Justifiée",
  usage_personnel: "Usage personnel confirmé",
  faux_positif: "Faux positif",
};

/** Variante de `Badge` (DESIGN.md : 8 badges, aucun ad hoc). Une alerte
 * ouverte est le badge « alerte » ; une alerte en cours d'instruction attend
 * une décision (« à valider ») ; une alerte justifiée est confirmée par un
 * humain. Un usage personnel ou un faux positif est une issue classée sans
 * badge dédié dans le vocabulaire : le gris informatif `neutral`. */
export type VarianteEtat = "alert" | "pending" | "validated" | "neutral";

export function varianteEtat(etat: EtatAlerte): VarianteEtat {
  switch (etat) {
    case "ouverte":
      return "alert";
    case "en_instruction":
      return "pending";
    case "justifiee":
      return "validated";
    default:
      return "neutral";
  }
}

const MOTIF_MINIMUM = 3;

/** AXE-800 : chaque qualification porte le motif de l'expert, d'au moins
 * trois caractères une fois les espaces retirés. Renvoie le motif prêt à
 * envoyer, ou `null` s'il manque. */
export function motifValide(saisie: string): string | null {
  const motif = saisie.trim();
  return motif.length >= MOTIF_MINIMUM ? motif : null;
}

/** Date et moyen de paiement du mouvement, sur une ligne. */
export function metaAlerte(alerte: AlerteAnomalie): string {
  return [formatDate(alerte.date), libelleMoyenPaiement(alerte.moyen_paiement ?? null)]
    .filter(Boolean)
    .join(" · ");
}

/** Une ligne d'historique (AXE-814) : date, état, qui, et le motif s'il y en a un.
 * Un état inconnu du client reste affiché tel quel plutôt que caché. */
export function phraseEvenement(evenement: EvenementAnomalie): string {
  const etat = LIBELLE_ETAT[evenement.etat as EtatAlerte] ?? evenement.etat;
  const motif = evenement.commentaire ? ` · « ${evenement.commentaire} »` : "";
  return `${formatDate(evenement.le)} · ${etat} · ${evenement.acteur}${motif}`;
}
