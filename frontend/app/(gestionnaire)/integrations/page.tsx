"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { BranchementsType } from "@/components/Branchements";
import {
  lireCategorisation,
  listerBranchements,
  obtenirSessionGestionnaire,
  type Branchement,
} from "@/lib/auth-gestionnaire";
import { ORDRE_TYPES } from "@/lib/branchements";
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

/** AXE-872 : chaque intégration peut avoir plusieurs accès (plusieurs SMTP,
 * plusieurs comptes Digifactory…). Un accès par défaut par type ; chaque
 * entreprise peut en choisir un autre depuis sa fiche. Digifactory reste le
 * canal bancaire : l'app chauffeur ne propose pas de connecter sa banque. */
export default function IntegrationsPage() {
  const router = useRouter();
  const [categorisation, setCategorisation] = useState<EtatCategorisation | null>(null);
  const [branchements, setBranchements] = useState<Branchement[]>([]);
  const droit = useDroitGestionnaire();

  useEffect(() => {
    if (obtenirSessionGestionnaire() === null) {
      router.replace("/connexion");
      return;
    }
    let actif = true;
    listerBranchements()
      .then((liste) => {
        if (actif) setBranchements(liste);
      })
      .catch(() => {
        // Non lus : chaque type s'affiche « À brancher ».
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
        Chaque intégration peut avoir plusieurs accès. Celui « par défaut » sert à toutes les
        entreprises, sauf celles qui en choisissent un autre dans leur fiche.
      </p>
      <ul className="mt-8">
        {ORDRE_TYPES.map((type) => (
          <BranchementsType
            key={type}
            type={type}
            branchements={branchements.filter((b) => b.type === type)}
            admin={droit.admin}
            onChange={setBranchements}
          />
        ))}
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
