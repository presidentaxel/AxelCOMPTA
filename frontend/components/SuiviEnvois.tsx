"use client";

import { useEffect, useState } from "react";

import { lireEnvois, type EnvoiRappel } from "@/lib/auth-gestionnaire";
import { formatDate } from "@/lib/format";

const STATUTS: Record<EnvoiRappel["statut"], string> = {
  en_attente: "en cours d'envoi",
  envoye: "envoyé",
  echec: "échec",
  ignore: "non envoyé",
};

/** AXE-808 : ce qui est parti vers l'entreprise, et ce qui a échoué (avec la
 * raison). Un statut, jamais le contenu du message. */
export function SuiviEnvois({ dossierId }: { dossierId: string }) {
  const [envois, setEnvois] = useState<EnvoiRappel[] | null>(null);

  useEffect(() => {
    let actif = true;
    lireEnvois(dossierId)
      .then((lus) => {
        if (actif) setEnvois(lus);
      })
      .catch(() => {
        if (actif) setEnvois([]);
      });
    return () => {
      actif = false;
    };
  }, [dossierId]);

  if (!envois || envois.length === 0) return null;
  return (
    <ul className="mt-3 space-y-1" aria-label="Rappels envoyés">
      {envois.slice(0, 5).map((envoi, index) => (
        <li key={`${envoi.le}-${index}`} className="text-xs text-subtle">
          {envoi.canal === "mail" ? "E-mail" : "SMS"} · {STATUTS[envoi.statut]}
          {envoi.le ? ` · ${formatDate(envoi.le.slice(0, 10))}` : ""}
          {envoi.raison ? ` · ${envoi.raison}` : ""}
        </li>
      ))}
    </ul>
  );
}
