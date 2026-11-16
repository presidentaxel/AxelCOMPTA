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

/** AXE-946 : le droit lu une fois par session et par compte, gardé en
 * mémoire : changer de page ne relit plus toute l'équipe (lent). */
let enCache: { email: string; droit: DroitGestionnaire } | null = null;
let enCours: { email: string; promesse: Promise<DroitGestionnaire> } | null = null;

function lireDroit(email: string): Promise<DroitGestionnaire> {
  if (enCours?.email === email) return enCours.promesse;
  const promesse = listerMembres()
    .then((membres): DroitGestionnaire => {
      const moi = membres.find((membre) => membre.email.toLowerCase() === email.toLowerCase());
      const role = moi?.role ?? "admin";
      return { role, ecriture: role !== "lecture", admin: role === "admin" };
    })
    .catch((): DroitGestionnaire => ({ role: "lecture", ecriture: false, admin: false }))
    .then((droit) => {
      enCache = { email, droit };
      return droit;
    });
  enCours = { email, promesse };
  return promesse;
}

/** Rôle de la session dans l'équipe. Tant que la liste n'est pas lue, les
 * actions restent ouvertes : un admin ne les voit pas grisées une seconde.
 * Un échec de lecture ferme l'écriture, pour ne pas proposer un bouton en 403. */
export function useDroitGestionnaire(): DroitGestionnaire {
  const [droit, setDroit] = useState<DroitGestionnaire>(() => {
    const session = obtenirSessionGestionnaire();
    return session && enCache?.email === session.email ? enCache.droit : OUVERT;
  });

  useEffect(() => {
    const session = obtenirSessionGestionnaire();
    if (!session) return;
    let actif = true;
    lireDroit(session.email).then((lu) => actif && setDroit(lu));
    return () => {
      actif = false;
    };
  }, []);

  return droit;
}
