"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Etat } from "@/components/Etat";
import { Squelette } from "@/components/Squelette";
import {
  choisirDossierDeTest,
  listerDossiersDeTest,
  obtenirSession,
  type DossierDeTest,
} from "@/lib/auth-chauffeur";
import { messageEchecChargement } from "@/lib/session";

/** AXE-822 : « Quel dossier ? ». Réservé au compte de test : il ouvre
 * l'espace chauffeur d'un dossier de son portefeuille, en lecture seule. */
export default function ChoixDossierDeTestPage() {
  const router = useRouter();
  const [dossiers, setDossiers] = useState<DossierDeTest[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(() => {
    setErreur(null);
    setDossiers(null);
    listerDossiersDeTest()
      .then(setDossiers)
      .catch((exception: unknown) => setErreur(messageEchecChargement(exception, "Impossible de charger les dossiers.")));
  }, []);

  useEffect(() => {
    const session = obtenirSession();
    if (!session?.lecteurTest) {
      router.replace(session ? `/chauffeur/${session.dossierId}` : "/chauffeur/login");
      return;
    }
    // Premier chargement à l'ouverture de l'écran.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    charger();
  }, [charger, router]);

  function ouvrir(dossier: DossierDeTest) {
    choisirDossierDeTest(dossier.dossier_id, dossier.nom);
    router.push(`/chauffeur/${dossier.dossier_id}`);
  }

  return (
    <section aria-labelledby="titre-choix">
      <h1 id="titre-choix" className="text-xl font-semibold text-ink">
        Quel dossier ?
      </h1>
      <p className="mt-1 text-sm text-subtle">
        Compte de test : vous voyez l&apos;espace du chauffeur tel qu&apos;il le verrait, sans
        pouvoir rien changer.
      </p>
      {erreur && (
        <Etat type="erreur" message={erreur} onReessayer={charger} className="mt-6" />
      )}
      {!erreur && dossiers === null && (
        <div className="mt-6 space-y-3" aria-hidden>
          <Squelette className="h-14 w-full" />
          <Squelette className="h-14 w-full" />
          <Squelette className="h-14 w-full" />
        </div>
      )}
      {dossiers && dossiers.length === 0 && (
        <Etat
          type="vide"
          message="Aucun dossier dans ce portefeuille."
          action={{ libelle: "Réessayer", onClick: charger }}
          className="mt-6"
        />
      )}
      {dossiers && dossiers.length > 0 && (
        <ul className="mt-6 divide-y divide-hairline rounded-md border border-border bg-canvas">
          {dossiers.map((dossier) => (
            <li key={dossier.dossier_id}>
              <button
                type="button"
                onClick={() => ouvrir(dossier)}
                className="flex min-h-11 w-full items-baseline justify-between gap-3 px-4 py-3 text-left transition-colors duration-150 hover:bg-canvas-app"
              >
                <span className="min-w-0">
                  <span className="block truncate text-base font-semibold text-ink">
                    {dossier.nom}
                  </span>
                  <span className="block text-sm text-subtle">{dossier.forme_juridique}</span>
                </span>
                <span className="shrink-0 text-sm tabular-nums text-subtle">
                  {dossier.nb_operations} opération{dossier.nb_operations > 1 ? "s" : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
