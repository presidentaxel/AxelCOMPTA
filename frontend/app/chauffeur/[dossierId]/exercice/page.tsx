"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";

import { ClotureExerciceSection } from "@/components/ClotureExerciceSection";
import { ClotureSection } from "@/components/ClotureSection";
import { GreffeInpiSection } from "@/components/GreffeInpiSection";
import { PaieSection } from "@/components/PaieSection";
import { useDossierChauffeur } from "@/app/chauffeur/use-dossier";
import { Squelette, SqueletteLignes } from "@/components/Squelette";
import { fetchAvecAuthChauffeur } from "@/lib/auth-chauffeur";
import { formatDate } from "@/lib/format";
import type { AffectationVue } from "@/lib/types";

/** Exercice : le résultat, les documents, le dépôt et la signature.
 * Séparé de l'activité pour que le téléphone s'ouvre sur les opérations. */
export default function ExerciceChauffeurPage({
  params,
}: {
  params: Promise<{ dossierId: string }>;
}) {
  const { dossierId } = use(params);
  const { dossier } = useDossierChauffeur(dossierId);
  const fiche = dossier.statut === "pret" ? dossier.valeur : null;
  const periode =
    fiche?.exercice_debut && fiche.exercice_fin
      ? `${formatDate(fiche.exercice_debut)} – ${formatDate(fiche.exercice_fin)}`
      : null;

  return (
    <div>
      <h1 className="text-[28px] font-bold tracking-tight text-ink">Exercice</h1>
      {dossier.statut === "en_cours" && <Squelette className="mt-2 h-4 w-56" />}
      {periode && <p className="mt-2 text-sm text-subtle">{periode}</p>}
      {dossier.statut === "erreur" && <p className="mt-4 text-sm text-danger">{dossier.message}</p>}
      {fiche &&
        [fiche.alerte_regime, fiche.alerte_tva]
          .filter((alerte): alerte is string => alerte !== null)
          .map((alerte) => (
            <p
              key={alerte}
              className="mt-4 rounded-md border border-border bg-canvas p-3 text-sm text-ink"
            >
              {alerte}
            </p>
          ))}
      {fiche && fiche.regimes_a_venir.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm text-subtle">
          {fiche.regimes_a_venir.map((changement) => (
            <li key={changement.exercice}>
              Exercice {changement.exercice} : {changement.regime} ({changement.motif})
            </li>
          ))}
        </ul>
      )}
      <div className="mt-8">
        {dossier.statut === "en_cours" ? (
          <SqueletteLignes nombre={6} className="h-10 w-full" />
        ) : (
          fiche && (
            <>
              <ClotureSection dossier={fiche} />
              {fiche.depot_greffe && <GreffeInpiSection dossier={fiche} />}
              <ClotureExerciceSection dossierId={dossierId} onClos={() => window.location.reload()} />
              <LienAffectation dossierId={dossierId} />
              {fiche.paie_par_bulletin && <PaieSection dossierId={dossierId} />}
            </>
          )
        )}
      </div>
    </div>
  );
}

/** Après la clôture : l'affectation du résultat se décide sur son propre
 * écran (Louis, 2026-09-26). Rien ne s'affiche tant qu'il n'y a rien à
 * décider. */
function LienAffectation({ dossierId }: { dossierId: string }) {
  const [vue, setVue] = useState<AffectationVue | null>(null);

  useEffect(() => {
    fetchAvecAuthChauffeur<AffectationVue>(`/dossiers/${dossierId}/affectation`)
      .then(setVue)
      .catch(() => setVue(null));
  }, [dossierId]);

  if (!vue?.applicable) {
    return null;
  }
  return (
    <Link
      href={`/chauffeur/${dossierId}/resultat`}
      className="mt-8 block rounded-md border border-border bg-canvas p-3 text-sm text-ink"
    >
      Décider de l&apos;affectation de mon résultat {vue.annee_exercice} →
    </Link>
  );
}
