"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useDossierChauffeur } from "@/app/chauffeur/use-dossier";
import { FormulaireCompte } from "@/components/FormulaireCompte";
import { Squelette } from "@/components/Squelette";
import {
  changerEmailAvecJeton,
  deconnecter,
  definirMotDePasse,
  obtenirSession,
} from "@/lib/auth-chauffeur";

export default function CompteChauffeurPage() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [jeton, setJeton] = useState<string | null>(null);
  const [dossierId, setDossierId] = useState<string | null>(null);

  useEffect(() => {
    const session = obtenirSession();
    if (!session) {
      router.replace("/chauffeur/login");
      return;
    }
    // Lecture de localStorage : même pont que le layout chauffeur.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setEmail(session.email);
    setJeton(session.accessToken);
    setDossierId(session.dossierId);
  }, [router]);

  if (!email || !jeton) {
    return (
      <div>
        <Squelette className="h-4 w-48" />
        <Squelette className="mt-8 h-10 w-full" />
        <Squelette className="mt-4 h-10 w-full" />
        <Squelette className="mt-6 h-9 w-32" />
      </div>
    );
  }

  return (
    <div>
      {dossierId && <StatutDossier dossierId={dossierId} />}
      <FormulaireCompte
        email={email}
        onMotDePasse={definirMotDePasse}
        onEmail={(adresse) => changerEmailAvecJeton(jeton, adresse)}
      />
      <button
        type="button"
        className="mt-10 text-sm font-medium text-danger"
        onClick={() => {
          deconnecter();
          router.push("/chauffeur/login");
        }}
      >
        Se déconnecter
      </button>
    </div>
  );
}

function StatutDossier({ dossierId }: { dossierId: string }) {
  const { dossier } = useDossierChauffeur(dossierId);
  if (dossier.statut === "en_cours") return <Squelette className="mb-6 h-4 w-64" />;
  if (dossier.statut === "erreur") {
    return <p className="mb-6 text-sm text-danger">{dossier.message}</p>;
  }
  return (
    <p className="mb-6 text-sm text-subtle">
      {dossier.valeur.nom} · {dossier.valeur.forme_juridique} · {dossier.valeur.regime_libelle}
    </p>
  );
}
