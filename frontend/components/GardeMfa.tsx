"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { lireMoi, obtenirSessionGestionnaire } from "@/lib/auth-gestionnaire";
import { CHEMIN_DOUBLE_AUTHENTIFICATION } from "@/lib/mfa-code";

/** AXE-812 : un admin connecté sans code est envoyé sur l'écran de double
 * authentification. L'API le refuse de toute façon (403) : ceci n'évite que
 * des écrans pleins d'erreurs. */
export function GardeMfa() {
  const chemin = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (chemin === CHEMIN_DOUBLE_AUTHENTIFICATION || !obtenirSessionGestionnaire()) return;
    let actif = true;
    lireMoi()
      .then((moi) => {
        if (actif && moi.mfa_requise) {
          const retour = new URLSearchParams({ retour: chemin });
          router.replace(`${CHEMIN_DOUBLE_AUTHENTIFICATION}?${retour.toString()}`);
        }
      })
      .catch(() => {
        // Session absente ou serveur injoignable : la page le dira elle-même.
      });
    return () => {
      actif = false;
    };
  }, [chemin, router]);

  return null;
}
