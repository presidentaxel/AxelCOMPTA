"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { IntegrationEnvoi } from "@/components/IntegrationEnvoi";
import {
  lireCategorisation,
  lireIntegrationsEnvoi,
  obtenirSessionGestionnaire,
} from "@/lib/auth-gestionnaire";
import { useDroitGestionnaire } from "@/lib/use-droit";
import type { EtatCategorisation } from "@/lib/types";

const PREVUES = [
  {
    nom: "Rollee",
    detail: "Lirait les courses et les versements Uber, Bolt et Heetch de chaque chauffeur.",
  },
  {
    nom: "Bridge",
    detail: "Connecterait la banque en direct, en plus de Digifactory.",
  },
  {
    nom: "Volubile",
    detail: "Passerait les appels des relances configurées dans Rappels.",
  },
];

/** Digifactory est le canal bancaire du portefeuille : les comptes des
 * entreprises arrivent par lui, l'app chauffeur ne propose donc pas de
 * connecter sa banque. Les autres intégrations sont annoncées, pas branchées. */
export default function IntegrationsPage() {
  const router = useRouter();
  const [categorisation, setCategorisation] = useState<EtatCategorisation | null>(null);
  const [envoi, setEnvoi] = useState<Record<string, string>>({});
  const droit = useDroitGestionnaire();

  useEffect(() => {
    if (obtenirSessionGestionnaire() === null) {
      router.replace("/connexion");
      return;
    }
    let actif = true;
    lireIntegrationsEnvoi()
      .then((canaux) => {
        if (actif) setEnvoi(canaux);
      })
      .catch(() => {
        // Non lu : les deux canaux s'affichent « À brancher ».
      });
    lireCategorisation()
      .then((etat) => {
        if (actif) setCategorisation(etat);
      })
      .catch(() => {
        // L'état n'a pas pu être lu : on n'affiche rien plutôt qu'un faux « en ordre ».
      });
    return () => {
      actif = false;
    };
  }, [router]);

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-[28px] font-bold tracking-tight text-ink">Intégrations</h1>
      <p className="mt-2 text-sm text-subtle">
        Digifactory apporte les comptes bancaires des entreprises. Le reste n&apos;est pas encore
        connecté.
      </p>
      <ul className="mt-8">
        <li className="flex items-start justify-between gap-6 border-b border-hairline py-4">
          <span>
            <span className="block text-sm font-medium text-ink">Digifactory</span>
            <span className="mt-1 block text-sm text-subtle">
              Branché. Les opérations arrivent chaque heure ; l&apos;état de chaque banque est dans
              Connexions bancaires.
            </span>
          </span>
          <span className="shrink-0 text-xs text-subtle">Branché</span>
        </li>
        {categorisation && (
          <li className="flex items-start justify-between gap-6 border-b border-hairline py-4">
            <span>
              <span className="block text-sm font-medium text-ink">Catégorisation automatique</span>
              <span className="mt-1 block text-sm text-subtle">
                {categorisation.modele_charge
                  ? "Le modèle est chargé : il propose une catégorie quand aucune règle ne s'applique."
                  : (categorisation.raison ??
                    "Le modèle n'est pas chargé. La synchronisation est arrêtée.")}
              </span>
            </span>
            <span
              className={`shrink-0 text-xs ${categorisation.modele_charge ? "text-subtle" : "font-medium text-danger"}`}
            >
              {categorisation.modele_charge ? "Branché" : "Dégradée"}
            </span>
          </li>
        )}
        {(["mail", "sms"] as const).map((canal) => (
          <IntegrationEnvoi
            key={canal}
            canal={canal}
            branche={envoi[canal]}
            admin={droit.admin}
            onBranche={setEnvoi}
          />
        ))}
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
