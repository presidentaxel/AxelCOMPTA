/** `link-action` (DESIGN.md § Liens et surlignage) : signal, 600, souligné de
 * 2 px décalé de 3 px, `signal-deep` au survol. Le soulignement est ce qui
 * distingue le lien : `signal` ne distingue jamais seul. L'anneau de focus est
 * détaché (un lien n'a pas de bordure à colorer). */
export const LIEN_ACTION =
  "rounded-sm font-semibold text-signal underline decoration-2 underline-offset-[3px] outline-none transition-colors duration-100 hover:text-signal-deep focus-visible:shadow-focus-detache motion-reduce:transition-none";

/** Texte de couleur d'un montant : rouge et signe moins en dessous de zéro,
 * vert sinon. Le signe est dans le texte (`formatMontant`), la couleur
 * ne porte jamais seule le sens. */
export function couleurMontant(centimes: number): string {
  return centimes < 0 ? "text-amount-negative" : "text-amount-positive";
}
