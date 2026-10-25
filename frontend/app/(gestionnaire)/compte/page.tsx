"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { FormulaireCompte } from "@/components/FormulaireCompte";
import { Squelette } from "@/components/Squelette";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  changerEmailGestionnaire,
  changerMotDePasseGestionnaire,
  lireNomPortefeuille,
  obtenirSessionGestionnaire,
  renommerPortefeuille,
} from "@/lib/auth-gestionnaire";

export default function CompteGestionnairePage() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [nom, setNom] = useState("");
  const [infoNom, setInfoNom] = useState<string | null>(null);

  useEffect(() => {
    const session = obtenirSessionGestionnaire();
    if (!session) {
      router.replace("/connexion");
      return;
    }
    // Lecture de localStorage : même pont que le layout chauffeur.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setEmail(session.email);
    lireNomPortefeuille()
      .then(setNom)
      .catch(() => undefined);
  }, [router]);

  if (!email) {
    return (
      <div className="mx-auto grid max-w-5xl items-start gap-12 lg:grid-cols-3">
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
    <div className="mx-auto grid max-w-5xl items-start gap-12 lg:grid-cols-3">
      <form
        className="space-y-4 lg:col-span-2"
        onSubmit={async (evenement) => {
          evenement.preventDefault();
          setInfoNom(null);
          try {
            setNom(await renommerPortefeuille(nom.trim()));
            setInfoNom("Nom enregistré.");
          } catch (exception) {
            setInfoNom(exception instanceof Error ? exception.message : "Échec de l'enregistrement.");
          }
        }}
      >
        <label className="block text-sm font-medium text-ink" htmlFor="nom-orga">
          Nom de l&apos;organisation
        </label>
        <Input id="nom-orga" value={nom} onChange={(evenement) => setNom(evenement.target.value)} required />
        <Button type="submit" size="sm">
          Enregistrer
        </Button>
        {infoNom && <p className="text-sm text-subtle">{infoNom}</p>}
      </form>
      <div>
      <FormulaireCompte
        email={email}
        onMotDePasse={changerMotDePasseGestionnaire}
        onEmail={changerEmailGestionnaire}
      />
      </div>
    </div>
  );
}
