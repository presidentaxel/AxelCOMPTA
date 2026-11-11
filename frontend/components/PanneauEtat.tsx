import Link from "next/link";

import { Button } from "@/components/ui/button";

/** Action d'un panneau d'état : un bouton, ou un lien interne. */
export type ActionPanneau = {
  libelle: string;
  onClick?: () => void;
  href?: string;
};

/** État d'un écran du gestionnaire (DESIGN.md › `empty-state`) : une erreur
 * ou un vide, en une phrase humaine et toujours une action, jamais une page
 * blanche ni un code brut. Pour l'espace chauffeur, `Etat` pose le même
 * contrat en cibles de 44 px pleine largeur.
 *
 * Le vide est sur fond canvas, cerné d'un filet ; l'erreur prend le filet
 * `danger` et s'annonce aux lecteurs d'écran (`role="alert"`). */
export function PanneauEtat({
  type,
  message,
  action,
}: {
  type: "erreur" | "vide";
  message: string;
  action: ActionPanneau;
}) {
  return (
    <div
      role={type === "erreur" ? "alert" : undefined}
      className={`rounded-lg border bg-canvas px-6 py-12 text-center ${
        type === "erreur" ? "border-danger-border" : "border-border"
      }`}
    >
      <p className={`text-sm ${type === "erreur" ? "text-ink" : "text-muted"}`}>{message}</p>
      {action.href ? (
        <Button asChild variant="secondary" className="mt-4">
          <Link href={action.href} onClick={action.onClick}>
            {action.libelle}
          </Link>
        </Button>
      ) : (
        <Button type="button" variant="secondary" className="mt-4" onClick={action.onClick}>
          {action.libelle}
        </Button>
      )}
    </div>
  );
}
