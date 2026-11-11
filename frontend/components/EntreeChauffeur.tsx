import type { ReactNode } from "react";

/** Habillage des écrans d'entrée du chauffeur (connexion, invitation
 * inutilisable) : titre de 28 px, texte de 16 px, bouton d'envoi de 48 px,
 * liens d'action soulignés.
 *
 * `FormulaireConnexion` et `SuitesAuth` sont partagés avec le gestionnaire et
 * posent leurs propres tailles (titre 20 px, texte 14 px, bouton 36/44 px) :
 * on les regroupe ici par sélecteurs plutôt que de les dupliquer. Les règles
 * descendantes (`.x h1`) l'emportent sur les classes de l'élément (`.text-xl`).
 * Quand ces composants accepteront une taille « grand », ce gabarit disparaît. */
const GABARIT = [
  "[&_h1]:text-[28px] [&_h1]:font-semibold [&_h1]:leading-tight [&_h1]:tracking-[-0.02em]",
  "[&_h1]:mb-2",
  "[&_p]:text-base [&_label]:text-base",
  "[&_[type=submit]]:h-12 [&_[type=submit]]:text-base",
  // « link-action » (DESIGN.md) : orange, gras, souligné de 2 px décalé de 3 px.
  "[&_:is(a,button[type=button])]:text-base [&_:is(a,button[type=button])]:font-semibold",
  "[&_:is(a,button[type=button])]:underline [&_:is(a,button[type=button])]:decoration-2",
  "[&_:is(a,button[type=button])]:underline-offset-[3px]",
  "[&_:is(a,button[type=button]):hover]:text-signal-deep",
].join(" ");

export function EntreeChauffeur({ children }: { children: ReactNode }) {
  return <div className={GABARIT}>{children}</div>;
}
