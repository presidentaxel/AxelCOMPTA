import type { NouveauChauffeur, Synchronisation } from "./types";

export function synchroEnCours(synchro: Synchronisation | null): boolean {
  return synchro !== null && (synchro.statut === "en_attente" || synchro.statut === "en_cours");
}

/** La phrase sous le bouton « Synchroniser ». */
export function phraseSynchro(synchro: Synchronisation | null, date: (iso: string) => string): string | null {
  if (synchro === null) return null;
  if (synchro.statut === "en_attente") return "Synchronisation demandée…";
  if (synchro.statut === "en_cours") return "Synchronisation en cours…";
  if (synchro.statut === "echec") return `La synchronisation a échoué : ${synchro.erreur ?? "erreur inconnue"}.`;
  const quand = synchro.terminee_le ? ` (${date(synchro.terminee_le)})` : "";
  return `Synchronisé${quand} : ${synchro.resultat ?? "terminé"}.`;
}

/** À valider : ni ignorés, ni déjà acceptés, et pas une société cessée. */
export function aValider(contacts: NouveauChauffeur[]): NouveauChauffeur[] {
  return contacts.filter((c) => c.decision === null && !c.cessee);
}

/** Les chauffeurs « évidents » (activité VTC, aucun avertissement), pour
 * « Ajouter les chauffeurs VTC » en un clic. */
export function chauffeursEvidents(contacts: NouveauChauffeur[]): NouveauChauffeur[] {
  return aValider(contacts).filter((c) => c.avertissements.length === 0);
}

export function ignores(contacts: NouveauChauffeur[]): NouveauChauffeur[] {
  return contacts.filter((c) => c.decision === "ignorer");
}
