"use client";

import { useRouter } from "next/navigation";

import { FormulaireConnexion } from "@/components/FormulaireConnexion";
import { PageAcces } from "@/components/PageAcces";
import {
  connexionGestionnaire,
  lireMoi,
  tracerConnexionGestionnaire,
} from "@/lib/auth-gestionnaire";
import { CHEMIN_DOUBLE_AUTHENTIFICATION } from "@/lib/mfa-code";
import { cheminDeRetour } from "@/lib/session";

/** Connexion gestionnaire (doc 03 §7). Hors du groupe `(gestionnaire)` pour
 * ne pas hériter de la barre de navigation avant d'être connecté : la marque
 * vient du cadre d'accès, pas du formulaire (le chauffeur a la sienne). */
export default function ConnexionGestionnairePage() {
  const router = useRouter();

  return (
    <PageAcces>
      <FormulaireConnexion
        titre="Connexion gestionnaire"
        sousTitre="Accédez à l'état de votre portefeuille."
        cote="gestionnaire"
        onConnecte={async (email, motDePasse) => {
          await connexionGestionnaire(email, motDePasse);
          await tracerConnexionGestionnaire();
          const retour = cheminDeRetour(window.location.search, "/");
          const moi = await lireMoi().catch(() => null);
          // AXE-812 : un admin saisit son code (ou s'enrôle) avant d'entrer.
          router.replace(
            moi?.mfa_requise
              ? `${CHEMIN_DOUBLE_AUTHENTIFICATION}?${new URLSearchParams({ retour }).toString()}`
              : retour,
          );
        }}
      />
    </PageAcces>
  );
}
