"use client";

import { useEffect, useState } from "react";

import { listerMembres, obtenirSessionGestionnaire } from "@/lib/auth-gestionnaire";

export type DroitGestionnaire = {
  role: "admin" | "membre" | "lecture" | "expert_comptable" | null;
  /** Lecture consulte. Membre et admin écrivent. */
  ecriture: boolean;
  admin: boolean;
};

const OUVERT: DroitGestionnaire = { role: null, ecriture: true, admin: true };

/** Rôle de la session dans l'équipe. Tant que la liste n'est pas lue, les
 * actions restent ouvertes : un admin ne les voit pas grisées une seconde.
 * Un échec de lecture ferme l'écriture, pour ne pas proposer un bouton en 403. */
export function useDroitGestionnaire(): DroitGestionnaire {
  const [droit, setDroit] = useState<DroitGestionnaire>(OUVERT);

  useEffect(() => {
    const session = obtenirSessionGestionnaire();
    if (!session) return;
    listerMembres()
      .then((membres) => {
        const moi = membres.find(
          (membre) => membre.email.toLowerCase() === session.email.toLowerCase(),
        );
        const role = moi?.role ?? "admin";
        setDroit({ role, ecriture: role !== "lecture", admin: role === "admin" });
      })
      .catch(() => setDroit({ role: "lecture", ecriture: false, admin: false }));
  }, []);

  return droit;
}
