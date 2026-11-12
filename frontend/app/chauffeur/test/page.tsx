"use client";

import { ChevronRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Etat } from "@/components/Etat";
import { Squelette } from "@/components/Squelette";
import { TitreEcran } from "@/components/TitreEcran";
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
      <TitreEcran id="titre-choix" titre="Quel dossier ?">
        Compte de test : vous voyez l&apos;espace du chauffeur tel qu&apos;il le verrait, sans
        pouvoir rien changer.
      </TitreEcran>
      {erreur && <Etat type="erreur" message={erreur} onReessayer={charger} className="mt-0" />}
      {!erreur && dossiers === null && (
        <div className="space-y-3" aria-hidden>
          <Squelette className="h-16 w-full" />
          <Squelette className="h-16 w-full" />
          <Squelette className="h-16 w-full" />
        </div>
      )}
      {dossiers && dossiers.length === 0 && (
        <Etat
          type="vide"
          message="Aucun dossier dans ce portefeuille."
          action={{ libelle: "Réessayer", onClick: charger }}
          className="mt-0"
        />
      )}
      {dossiers && dossiers.length > 0 && (
        <ul className="divide-y divide-hairline overflow-hidden rounded-lg border border-border bg-canvas">
          {dossiers.map((dossier) => (
            <li key={dossier.dossier_id}>
              <button
                type="button"
                onClick={() => ouvrir(dossier)}
                className="flex min-h-16 w-full items-center justify-between gap-3 px-4 py-3 text-left outline-none transition-colors duration-150 hover:bg-canvas-app focus-visible:bg-canvas-app focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-signal"
              >
                <span className="min-w-0">
                  <span className="block truncate text-base font-semibold text-ink">
                    {dossier.nom}
                  </span>
                  <span className="block text-sm text-subtle">
                    {dossier.forme_juridique} · {dossier.nb_operations} opération
                    {dossier.nb_operations > 1 ? "s" : ""}
                  </span>
                </span>
                <ChevronRight className="h-5 w-5 shrink-0 text-muted" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
