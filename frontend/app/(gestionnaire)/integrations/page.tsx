"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  ErreurAuthGestionnaire,
  lireParametresDemo,
  obtenirSessionGestionnaire,
  reglerDigifactoryDemo,
} from "@/lib/auth-gestionnaire";
import { useDroitGestionnaire } from "@/lib/use-droit";

const PREVUES = [
  {
    nom: "Bridge",
    detail: "Connexion bancaire directe, en plus du canal déjà utilisé pour le pilote.",
  },
  {
    nom: "Volubile",
    detail: "Appels automatiques pour les rappels configurés dans Rappels.",
  },
  {
    nom: "SMS",
    detail: "Envoi des rappels par SMS.",
  },
  {
    nom: "E-mail",
    detail: "Envoi des rappels par e-mail, distinct de l'invitation de compte.",
  },
];

/** Digifactory est un faux canal : branché par défaut, l'app chauffeur ne
 * propose pas de connecter sa banque. Le réglage se change ici. */
export default function IntegrationsPage() {
  const router = useRouter();
  const droit = useDroitGestionnaire();
  const [branche, setBranche] = useState<boolean | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  useEffect(() => {
    if (obtenirSessionGestionnaire() === null) {
      router.replace("/connexion");
      return;
    }
    lireParametresDemo()
      .then((parametres) => setBranche(parametres.digifactory_branche))
      .catch((exception: unknown) => {
        if (exception instanceof ErreurAuthGestionnaire) {
          router.replace("/connexion");
          return;
        }
        setErreur("Impossible de lire les paramètres.");
      });
  }, [router]);

  async function basculer() {
    if (branche === null || !droit.ecriture) return;
    if (branche && !window.confirm("Débrancher Digifactory ? Les entreprises verront « Connecter ma banque ».")) {
      return;
    }
    setEnCours(true);
    setErreur(null);
    try {
      const parametres = await reglerDigifactoryDemo(!branche);
      setBranche(parametres.digifactory_branche);
    } catch (exception) {
      if (exception instanceof ErreurAuthGestionnaire) {
        router.replace("/connexion");
        return;
      }
      setErreur("Impossible d'enregistrer le réglage.");
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-[28px] font-bold tracking-tight text-ink">Intégrations</h1>
      <p className="mt-2 text-sm text-subtle">
        Digifactory est un canal de démonstration. Le reste n&apos;est pas connecté.
      </p>
      {erreur && <p className="mt-4 text-sm text-danger">{erreur}</p>}
      <ul className="mt-8">
        <li className="flex items-center justify-between gap-6 border-b border-hairline py-4">
          <span>
            <span className="block text-sm font-medium text-ink">Digifactory</span>
            <span className="mt-1 block text-sm text-subtle">
              {branche === null
                ? "Lecture du canal…"
                : branche
                  ? "Branché. Les entreprises ne voient pas « Connecter ma banque »."
                  : "Débranché. L'app propose « Connecter ma banque »."}
            </span>
          </span>
          <Button
            type="button"
            variant="secondary"
            disabled={branche === null || enCours || !droit.ecriture}
            onClick={basculer}
          >
            {branche === null ? "…" : branche ? "Débrancher" : "Brancher"}
          </Button>
        </li>
        {PREVUES.map((integration) => (
          <li
            key={integration.nom}
            className="flex items-start justify-between gap-6 border-b border-hairline py-4"
          >
            <span>
              <span className="block text-sm font-medium text-ink">{integration.nom}</span>
              <span className="mt-1 block text-sm text-subtle">{integration.detail}</span>
            </span>
            <span className="shrink-0 text-xs text-subtle">Prévu</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
