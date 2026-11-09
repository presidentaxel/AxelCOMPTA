"use client";

import { useRouter } from "next/navigation";

import { FormulaireConnexion } from "@/components/FormulaireConnexion";
import {
  connexionGestionnaire,
  lireMoi,
  tracerConnexionGestionnaire,
} from "@/lib/auth-gestionnaire";
import { cheminDeRetour } from "@/lib/session";

/** Connexion gestionnaire (doc 03 §7). Hors du groupe `(gestionnaire)` pour
 * ne pas hériter de la Sidebar/TopBar avant d'être connecté. */
export default function ConnexionGestionnairePage() {
  const router = useRouter();

  return (
    <main className="mx-auto mt-24 max-w-sm px-4">
      <FormulaireConnexion
        titre="Connexion gestionnaire"
        sousTitre="Accédez à l'état de votre portefeuille."
        onConnecte={async (email, motDePasse) => {
          await connexionGestionnaire(email, motDePasse);
          await tracerConnexionGestionnaire();
          const retour = cheminDeRetour(window.location.search, "/");
          const moi = await lireMoi().catch(() => null);
          // AXE-812 : un admin saisit son code (ou s'enrôle) avant d'entrer.
          router.replace(
            moi?.mfa_requise ? `/securite?${new URLSearchParams({ retour }).toString()}` : retour,
          );
        }}
      />
    </main>
  );
}
