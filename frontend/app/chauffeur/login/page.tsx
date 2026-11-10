"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { FormulaireConnexion } from "@/components/FormulaireConnexion";
import {
  connexionParMotDePasse,
  obtenirSession,
  tracerConnexionChauffeur,
} from "@/lib/auth-chauffeur";
import { cheminDuDossier } from "@/lib/compte-de-test";
import { cheminDeRetour, sessionAExpire } from "@/lib/session";

/** doc 19 §5.2 : e-mail + mot de passe, ou lien magique. Pas de
 * self-signup : le lien magique refuse de créer un compte. */
export default function ConnexionChauffeurPage() {
  const router = useRouter();
  const [affiche, setAffiche] = useState(false);

  useEffect(() => {
    const recherche = window.location.search;
    const session = obtenirSession();
    if (session && !sessionAExpire(recherche)) {
      router.replace(cheminDeRetour(recherche, cheminDuDossier(session)));
      return;
    }
    // La session n'existe que dans le navigateur : on attend pour ne pas
    // montrer le formulaire à quelqu'un déjà connecté.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setAffiche(true);
  }, [router]);

  if (!affiche) return null;

  return (
    <FormulaireConnexion
      titre="Connexion"
      sousTitre="Retrouvez vos transactions et vos justificatifs."
      onConnecte={async (email, motDePasse) => {
        const session = await connexionParMotDePasse(email, motDePasse);
        void tracerConnexionChauffeur();
        // Un retour vers le dossier d'un autre renvoie de toute façon vers le
        // sien (`use-dossier.ts`). `replace` : le bouton retour ne ramène pas
        // au formulaire.
        router.replace(cheminDeRetour(window.location.search, cheminDuDossier(session)));
      }}
    />
  );
}
