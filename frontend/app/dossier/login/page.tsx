"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { EntreeChauffeur } from "@/components/EntreeChauffeur";
import { FormulaireConnexion } from "@/components/FormulaireConnexion";
import {
  connexionParMotDePasse,
  decoderChargeUtileJwt,
  obtenirSession,
  tracerConnexionChauffeur,
} from "@/lib/auth-chauffeur";
import { cheminApresChauffeur } from "@/lib/auth-lien";
import { deconnecterGestionnaire } from "@/lib/auth-gestionnaire";
import { coteOuverte } from "@/lib/cote-connexion";
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
      router.replace(cheminDeRetour(recherche, cheminApresChauffeur(session.accessToken, session)));
      return;
    }
    // La session n'existe que dans le navigateur : on attend pour ne pas
    // montrer le formulaire à quelqu'un déjà connecté.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setAffiche(true);
  }, [router]);

  if (!affiche) return null;

  return (
    <div className="pt-4">
      <EntreeChauffeur>
        <FormulaireConnexion
          titre="Connexion"
          sousTitre="Retrouvez vos transactions et vos justificatifs."
          cote="chauffeur"
          onConnecte={async (email, motDePasse) => {
            const session = await connexionParMotDePasse(email, motDePasse);
            const charge = decoderChargeUtileJwt(session.accessToken);
            if (
              session.lecteurTest ||
              coteOuverte(charge.app_metadata, "gestionnaire") !== "gestionnaire"
            ) {
              deconnecterGestionnaire();
            }
            void tracerConnexionChauffeur();
            router.replace(
              cheminDeRetour(window.location.search, cheminApresChauffeur(session.accessToken, session)),
            );
          }}
        />
      </EntreeChauffeur>
    </div>
  );
}
