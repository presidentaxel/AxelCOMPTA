"use client";

import { useCallback, useEffect, useState } from "react";

import { Etat } from "@/components/Etat";
import { Squelette } from "@/components/Squelette";
import { fetchAvecAuthChauffeur } from "@/lib/auth-chauffeur";
import { formatDate } from "@/lib/format";
import { messageEchecChargement } from "@/lib/session";

type ActeAcces = { type: string; reference: string; par_vous: boolean; le: string };

const ACTES: Record<string, string> = {
  export: "Téléchargement",
  consultation: "Consultation",
  connexion: "Connexion",
};

/** AXE-812 : le dirigeant voit qui a consulté ou exporté son dossier, et
 * quand. Lu dans le journal d'audit, qui ne se modifie pas. */
export function AccesDossier({ dossierId }: { dossierId: string }) {
  const [actes, setActes] = useState<ActeAcces[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(() => {
    setErreur(null);
    fetchAvecAuthChauffeur<ActeAcces[]>(`/dossiers/${dossierId}/acces`)
      .then(setActes)
      .catch((exception: unknown) =>
        setErreur(messageEchecChargement(exception, "Impossible de lire l'historique.")),
      );
  }, [dossierId]);

  useEffect(() => {
    // Premier chargement à l'ouverture de l'écran.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    charger();
  }, [charger]);

  return (
    <section aria-labelledby="titre-acces" className="mt-10">
      <h2 id="titre-acces" className="text-base font-semibold text-ink">
        Accès à votre dossier
      </h2>
      <p className="mt-1 text-sm text-subtle">Connexions et téléchargements, les plus récents d&apos;abord.</p>
      {erreur && <Etat type="erreur" message={erreur} onReessayer={charger} />}
      {!erreur && actes === null && <Squelette className="mt-4 h-10 w-full" />}
      {actes && actes.length === 0 && (
        <p className="mt-4 text-sm text-subtle">Aucun accès enregistré pour l&apos;instant.</p>
      )}
      {actes && actes.length > 0 && (
        <ul className="mt-4 divide-y divide-hairline">
          {actes.slice(0, 20).map((acte) => (
            <li key={`${acte.le}-${acte.reference}`} className="py-2 text-sm">
              <span className="text-ink">
                {ACTES[acte.type] ?? acte.type}
                {acte.type === "export" ? ` · ${acte.reference}` : ""}
              </span>
              <span className="block text-subtle">
                {formatDate(acte.le.slice(0, 10))} · {acte.par_vous ? "vous" : "une autre personne"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
