"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { FormulaireConnexion } from "@/components/FormulaireConnexion";
import { Squelette } from "@/components/Squelette";
import { connexionParMotDePasse, obtenirSession } from "@/lib/auth-chauffeur";
import { cheminDeRetour } from "@/lib/session";

/** doc 19 §5.2 : e-mail + mot de passe, ou lien magique. Pas de
 * self-signup : le lien magique refuse de créer un compte. Une session
 * déjà ouverte ne revoit pas le formulaire. */
export default function ConnexionChauffeurPage() {
  const router = useRouter();
  const [pret, setPret] = useState(false);

  useEffect(() => {
    const session = obtenirSession();
    if (session) {
      router.replace(`/chauffeur/${session.dossierId}`);
      return;
    }
    // Lecture de la session navigateur, même pont que le layout chauffeur.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPret(true);
  }, [router]);

  if (!pret) {
    return <Squelette className="h-40 w-full" />;
  }

  return (
    <FormulaireConnexion
      titre="Connexion"
      sousTitre="Retrouvez vos transactions et vos justificatifs."
      onConnecte={async (email, motDePasse) => {
        const session = await connexionParMotDePasse(email, motDePasse);
        // Un retour vers le dossier d'un autre renvoie de toute façon vers le
        // sien (`use-dossier.ts`). replace : le bouton retour ne ramène pas
        // au formulaire.
        router.replace(cheminDeRetour(window.location.search, `/chauffeur/${session.dossierId}`));
      }}
    />
  );
}
