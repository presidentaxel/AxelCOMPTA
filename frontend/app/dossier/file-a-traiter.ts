import { ticketPrioritaire } from "@/lib/tickets";
import type { TransactionVue } from "@/lib/types";

/** Fenêtre pour annuler un tap avant qu'il ne devienne une décision. */
export const DELAI_ANNULATION_MS = 6_000;

/** Tickets déjà classés : ils ne sont pas aussi une question. */
export function ticketsSeuls(operations: readonly TransactionVue[]): TransactionVue[] {
  return operations.filter(
    (operation) => ticketPrioritaire(operation) && operation.statut !== "à trancher",
  );
}

/** Questions encore à l'écran. Celles qu'on vient de trancher restent masquées
 * le temps que le serveur les confirme, ou après une annulation ratée. */
export function questionsRestantes(
  aVerifier: readonly TransactionVue[],
  horsFile: readonly string[],
): TransactionVue[] {
  const masquees = new Set(horsFile);
  return aVerifier.filter((operation) => !masquees.has(operation.ecriture_id));
}

/** `position` est la carte affichée. `total` compte aussi les tickets,
 * qui ne sont pas une carte chacun. */
export function compteurFile(
  restantes: number,
  decidees: number,
  tickets: number,
): { position: number; total: number } {
  const total = restantes + decidees + tickets;
  const position = restantes === 0 ? 0 : decidees + 1;
  return { position, total };
}

/** `suite` prolonge l'annonce (« Suivante : … », « Il reste des tickets. »). */
export function annonceClassee(nom: string, libelle: string, suite: string | null): string {
  const faite = `« ${nom} » classée en « ${libelle} ».`;
  return suite ? `${faite} ${suite}` : faite;
}

export function annonceAnnulee(nom: string): string {
  return `Décision annulée. « ${nom} » est de nouveau à traiter.`;
}
