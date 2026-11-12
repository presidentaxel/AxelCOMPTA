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
    <div className="mx-auto max-w-4xl">
      <h1 className="text-[22px] font-bold tracking-tight text-ink">Intégrations</h1>
      <p className="mt-2 max-w-2xl text-sm text-subtle">
        Plusieurs accès par type. Celui par défaut sert à toutes les entreprises. Une entreprise
        peut en choisir un autre dans sa fiche.
      </p>
      <div className="mt-8 space-y-4">
        {ORDRE_TYPES.map((type) => (
          <BranchementsType
            key={type}
            type={type}
            branchements={branchements.filter((b) => b.type === type)}
            admin={droit.admin}
            onChange={setBranchements}
          />
        ))}
      </div>
      {categorisation && (
        <p className="mt-8 text-sm text-subtle">
          Catégorisation automatique :{" "}
          {categorisation.modele_charge
            ? "le modèle est chargé. Il propose une catégorie quand aucune règle ne s'applique."
            : (categorisation.raison ??
              "le modèle n'est pas chargé. La synchronisation est arrêtée.")}
        </p>
      )}
      <section className="mt-10">
        <h2 className="text-sm font-medium text-ink">Pas encore disponibles</h2>
        <ul className="mt-3 divide-y divide-hairline border-y border-hairline">
          {PREVUES.map((integration) => (
            <li key={integration.nom} className="flex items-baseline justify-between gap-6 py-3">
              <span>
                <span className="text-sm text-ink">{integration.nom}</span>
                <span className="mt-0.5 block text-sm text-subtle">{integration.detail}</span>
              </span>
              <span className="shrink-0 text-xs text-subtle">Prévu</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
