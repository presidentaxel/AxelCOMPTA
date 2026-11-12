"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";

import { ClotureExerciceSection } from "@/components/ClotureExerciceSection";
import { ChiffresExercice, ClotureSection } from "@/components/ClotureSection";
import { GreffeInpiSection } from "@/components/GreffeInpiSection";
import { PaieSection } from "@/components/PaieSection";
import { ProvisionsCloture } from "@/components/ProvisionsCloture";
import { useDossierChauffeur } from "@/app/chauffeur/use-dossier";
import { Etat } from "@/components/Etat";
import { Squelette, SqueletteLignes } from "@/components/Squelette";
import { fetchAvecAuthChauffeur } from "@/lib/auth-chauffeur";
import { phraseOperationsRestantes, raisonApresCloture } from "@/lib/etapes-exercice";
import { formatDate } from "@/lib/format";
import type { AffectationVue, DividendesVue } from "@/lib/types";

/** Exercice : provisions, clôture, documents, greffe, puis l'affectation.
 * Chaque étape attend la précédente. Séparé de l'activité pour que le
 * téléphone s'ouvre sur les opérations. */
export default function ExerciceChauffeurPage({
  params,
}: {
  params: Promise<{ dossierId: string }>;
}) {
  const { dossierId } = use(params);
  const { dossier, recharger, reessayer } = useDossierChauffeur(dossierId);
  const [clos, setClos] = useState(false);
  const [revisionProvisions, setRevisionProvisions] = useState(0);
  const [suivi, setSuivi] = useState(dossierId);
  if (suivi !== dossierId) {
    setSuivi(dossierId);
    setClos(false);
    setRevisionProvisions(0);
  }
  const fiche = dossier.statut === "pret" ? dossier.valeur : null;
  const periode =
    fiche?.exercice_debut && fiche.exercice_fin
      ? `${formatDate(fiche.exercice_debut)} – ${formatDate(fiche.exercice_fin)}`
      : null;
  const comptesClos = Boolean(fiche?.cloture_faite) || clos;
  const operationsRestantes = fiche?.nb_a_trancher ?? 0;
  const raisonDocuments = fiche ? raisonApresCloture(operationsRestantes, comptesClos) : null;
  const raisonCloture = operationsRestantes > 0 ? phraseOperationsRestantes(operationsRestantes) : null;

  return (
    <div>
      <h1 className="text-[28px] font-bold tracking-tight text-ink">Exercice</h1>
      {dossier.statut === "en_cours" && <Squelette className="mt-2 h-4 w-56" />}
      {periode && <p className="mt-2 text-sm text-subtle">{periode}</p>}
      {fiche && fiche.tva_recettes_regime !== "franchise" && (
        <Link
          href={`/chauffeur/${dossierId}/tva`}
          className="mt-2 inline-flex min-h-11 items-center text-sm font-medium text-primary"
        >
          Ma TVA : déclaration de la période →
        </Link>
      )}
      <Link
        href={`/chauffeur/${dossierId}/ouverture`}
        className="mt-1 flex min-h-11 items-center text-sm font-medium text-primary"
      >
        Votre société existait avant ? Reprendre vos comptes →
      </Link>
      {dossier.statut === "erreur" && (
        <Etat type="erreur" message={dossier.message} onReessayer={reessayer} />
      )}
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
              <ChiffresExercice dossier={fiche} />
              <ProvisionsCloture
                dossierId={dossierId}
                onChange={() => {
                  setRevisionProvisions((valeur) => valeur + 1);
                  recharger();
                }}
              />
              <ClotureExerciceSection
                dossierId={dossierId}
                revision={revisionProvisions}
                raisonBlocage={raisonCloture}
                onClos={() => {
                  setClos(true);
                  recharger();
                }}
              />
              <ClotureSection
                dossier={fiche}
                comptesClos={comptesClos}
                operationsRestantes={operationsRestantes}
              />
              {fiche.depot_greffe && (
                <GreffeInpiSection dossier={fiche} raisonBlocage={raisonDocuments} />
              )}
              <LienAffectation
                dossierId={dossierId}
                comptesClos={comptesClos}
                raisonBlocage={raisonDocuments}
              />
              {fiche.paie_par_bulletin && <PaieSection dossierId={dossierId} />}
            </>
          )
        )}
      </div>
    </div>
  );
}

const LIEN =
  "mt-8 block min-h-11 rounded-md border border-border bg-canvas p-3 text-sm text-ink outline-none focus-visible:shadow-focus-detache";

/** L'affectation se décide sur son écran. Une fois décidée, « Mes dividendes »
 * reste accessible tant que le versement existe — y compris après la
 * déclaration 2777, pour retrouver l'échéance. */
function LienAffectation({
  dossierId,
  comptesClos,
  raisonBlocage,
}: {
  dossierId: string;
  comptesClos: boolean;
  raisonBlocage: string | null;
}) {
  const [affectation, setAffectation] = useState<AffectationVue | null>(null);
  const [dividendes, setDividendes] = useState<DividendesVue | null>(null);

  useEffect(() => {
    let annule = false;
    fetchAvecAuthChauffeur<AffectationVue>(`/dossiers/${dossierId}/affectation`)
      .then((vue) => {
        if (!annule) setAffectation(vue);
      })
      .catch(() => {
        if (!annule) setAffectation(null);
      });
    fetchAvecAuthChauffeur<DividendesVue>(`/dossiers/${dossierId}/dividendes`)
      .then((vue) => {
        if (!annule) setDividendes(vue);
      })
      .catch(() => {
        if (!annule) setDividendes(null);
      });
    return () => {
      annule = true;
    };
  }, [dossierId, comptesClos]);

  if (raisonBlocage) {
    return (
      <section className="mt-8 rounded-md border border-border bg-canvas p-3">
        <h2 className="text-sm font-medium text-ink">Affectation du résultat</h2>
        <p className="mt-1 text-sm text-ink">{raisonBlocage}</p>
      </section>
    );
  }
  if (affectation?.applicable) {
    return (
      <Link href={`/chauffeur/${dossierId}/resultat`} className={LIEN}>
        Décider de ce que je fais de mon résultat {affectation.annee_exercice} →
      </Link>
    );
  }
  if (dividendes?.applicable) {
    const annee = dividendes.annee_exercice ? ` ${dividendes.annee_exercice}` : "";
    return (
      <Link href={`/chauffeur/${dossierId}/resultat`} className={LIEN}>
        Mes dividendes{annee} →
      </Link>
    );
  }
  return null;
}
