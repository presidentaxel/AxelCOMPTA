"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { FormulaireCompte } from "@/components/FormulaireCompte";
import { Squelette } from "@/components/Squelette";
import {
  changerEmailGestionnaire,
  changerMotDePasseGestionnaire,
  obtenirSessionGestionnaire,
} from "@/lib/auth-gestionnaire";

export default function CompteGestionnairePage() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    const session = obtenirSessionGestionnaire();
    if (!session) {
      router.replace("/connexion");
      return;
    }
    // Lecture de localStorage : même pont que le layout chauffeur.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setEmail(session.email);
  }, [router]);

  if (!email) {
    return (
      <div className="grid items-start gap-8 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2" aria-hidden>
          <Squelette className="h-4 w-40" />
          <Squelette className="h-10 w-full" />
          <Squelette className="h-9 w-28" />
        </div>
        <div className="space-y-4" aria-hidden>
          <Squelette className="h-4 w-24" />
          <Squelette className="h-10 w-full" />
          <Squelette className="h-10 w-full" />
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-md">
      <FormulaireCompte
        email={email}
        onMotDePasse={changerMotDePasseGestionnaire}
        onEmail={changerEmailGestionnaire}
      />
      <p className="mt-6 text-sm text-subtle">
        Le nom de l&apos;organisation se modifie dans la barre, à gauche. Entrée enregistre, et un échec s&apos;affiche sous le nom.
      </p>
    </div>
  );
}
