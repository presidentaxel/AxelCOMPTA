import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";

/** Action d'un état vide : un bouton, ou un lien interne. */
export type ActionEtat = {
  libelle: string;
  onClick?: () => void;
  href?: string;
};

type Commun = { className?: string };

/**
 * État d'un écran chauffeur. Trois formes, et toujours une suite :
 * le squelette pendant le chargement, l'erreur (réseau ou serveur) avec
 * « Réessayer », le vide avec une phrase et une action.
 * Le bouton fait 44 px : ces écrans se tiennent au doigt.
 */
export function Etat(
  props: Commun &
    (
      | { type: "chargement"; children: ReactNode }
      | { type: "erreur"; message: string; onReessayer: () => void }
      | { type: "vide"; message: string; action: ActionEtat }
    ),
) {
  const className = props.className ?? "mt-6";
  if (props.type === "chargement") {
    return (
      <div className={className} role="status" aria-busy="true">
        <span className="sr-only">Chargement.</span>
        {props.children}
      </div>
    );
  }
  if (props.type === "erreur") {
    return (
      <div className={className} role="alert">
        <p className="text-sm text-danger">{props.message}</p>
        <Button type="button" variant="secondary" className="mt-3 h-11 w-full" onClick={props.onReessayer}>
          Réessayer
        </Button>
      </div>
    );
  }
  const { action } = props;
  const bouton = "mt-3 h-11 w-full";
  return (
    <div className={className}>
      <p className="text-sm text-subtle">{props.message}</p>
      {action.href ? (
        <Button asChild variant="secondary" className={bouton}>
          <Link href={action.href} onClick={action.onClick}>
            {action.libelle}
          </Link>
        </Button>
      ) : (
        <Button type="button" variant="secondary" className={bouton} onClick={action.onClick}>
          {action.libelle}
        </Button>
      )}
    </div>
  );
}
