"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useDossierChauffeur } from "@/app/chauffeur/use-dossier";
import { AccesDossier } from "@/components/AccesDossier";
import { ComptesBancaires } from "@/components/ComptesBancaires";
import { Etat } from "@/components/Etat";
import { FormulaireCompteChauffeur } from "@/components/FormulaireCompteChauffeur";
import { Squelette } from "@/components/Squelette";
import { TitreEcran } from "@/components/TitreEcran";
import { Button } from "@/components/ui/button";
import {
  changerEmailAvecJeton,
  deconnecter,
  definirMotDePasse,
  obtenirSession,
} from "@/lib/auth-chauffeur";

import { LiensJuridiques } from "@/components/LiensJuridiques";
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
      <Etat type="chargement" className="mt-0">
        <Squelette className="h-8 w-40" />
        <Squelette className="mt-3 h-4 w-64" />
        <Squelette className="mt-10 h-12 w-full" />
        <Squelette className="mt-4 h-12 w-full" />
      </Etat>
    );
  }

  return (
    <div>
      <TitreEcran titre="Compte" />
      {dossierId && <StatutDossier dossierId={dossierId} />}
      {dossierId && <ComptesBancaires dossierId={dossierId} />}
      {dossierId && <AccesDossier dossierId={dossierId} />}
      <FormulaireCompteChauffeur
        email={email}
        onMotDePasse={definirMotDePasse}
        onEmail={(adresse) => changerEmailAvecJeton(jeton, adresse)}
      />
      <Button
        type="button"
        size="lg"
        variant="secondary"
        className="mt-10 h-12 w-full text-base"
        onClick={() => {
          deconnecter();
          router.replace("/chauffeur/login");
        }}
      >
        Se déconnecter
      </Button>
      <LiensJuridiques className="mt-6" />
    </div>
  );
}

/** Qui est la société : une ligne sous le titre, en texte courant. */
function StatutDossier({ dossierId }: { dossierId: string }) {
  const { dossier, reessayer } = useDossierChauffeur(dossierId);
  if (dossier.statut === "en_cours") {
    return (
      <Etat type="chargement" className="mb-8 mt-0">
        <Squelette className="h-4 w-64" />
      </Etat>
    );
  }
  if (dossier.statut === "erreur") {
    return <Etat type="erreur" message={dossier.message} onReessayer={reessayer} className="mb-8 mt-0" />;
  }
  return (
    <p className="mb-8 text-base text-subtle">
      {dossier.valeur.nom} · {dossier.valeur.forme_juridique} · {dossier.valeur.regime_libelle}
    </p>
  );
}
