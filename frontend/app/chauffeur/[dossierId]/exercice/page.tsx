"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";

import { useDossierChauffeur } from "@/app/chauffeur/use-dossier";
import { ClotureExerciceSection } from "@/components/ClotureExerciceSection";
import { ClotureSection } from "@/components/ClotureSection";
import { EtatErreur } from "@/components/EtatChargement";
import { GreffeInpiSection } from "@/components/GreffeInpiSection";
import { PaieSection } from "@/components/PaieSection";
import { ProvisionsCloture } from "@/components/ProvisionsCloture";
import { ResultatACeJour } from "@/components/ResultatACeJour";
import { Squelette, SqueletteLignes } from "@/components/Squelette";
import { fetchAvecAuthChauffeur } from "@/lib/auth-chauffeur";
import { formatDate } from "@/lib/format";
import { messageVisible } from "@/lib/messages";
import type { AffectationVue, DividendesVue } from "@/lib/types";

/** Exercice : provisions, clôture, documents, dépôt, puis dividendes.
 * Une étape suivante reste visible, grisée, avec la raison. */
export default function ExerciceChauffeurPage({
  params,
}: {
  params: Promise<{ dossierId: string }>;
}) {
  const { dossierId } = use(params);
  const { dossier, reessayer, rafraichir } = useDossierChauffeur(dossierId);
  const [relecture, setRelecture] = useState(0);
  const fiche = dossier.statut === "pret" ? dossier.valeur : null;
  const periode =
    fiche?.exercice_debut && fiche.exercice_fin
      ? `${formatDate(fiche.exercice_debut)} – ${formatDate(fiche.exercice_fin)}`
      : null;
  const restantes = fiche?.nb_a_trancher ?? 0;
  const raisonOperations =
    restantes > 0
      ? `Il reste ${restantes} opération${restantes > 1 ? "s" : ""} à traiter.`
      : "Clôturez d'abord l'exercice.";
  const suitePrete = fiche !== null && fiche.cloture_faite && restantes === 0;

  return (
    <div>
      <h1 className="text-[28px] font-bold tracking-tight text-ink">Exercice</h1>
      {dossier.statut === "en_cours" && <Squelette className="mt-2 h-4 w-56" />}
      {periode && <p className="mt-2 text-sm text-subtle">{periode}</p>}
      {dossier.statut === "erreur" && <EtatErreur message={dossier.message} onReessayer={reessayer} />}
      {fiche && <ResultatACeJour centimes={fiche.resultat_cts} />}
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
              <section>
                <h2 className="text-base font-semibold text-ink">Charges pas encore passées</h2>
                <ProvisionsCloture
                  dossierId={dossierId}
                  onChange={() => {
                    setRelecture((n) => n + 1);
                    rafraichir();
                  }}
                />
              </section>
              <ClotureExerciceSection
                dossierId={dossierId}
                relecture={relecture}
                onClos={rafraichir}
              />
              <div className={suitePrete ? "" : "mt-8"}>
                <ClotureSection dossier={fiche} operationsRestantes={restantes} />
              </div>
              {fiche.depot_greffe && (
                <GreffeInpiSection
                  dossier={fiche}
                  bloque={!suitePrete}
                  raison={raisonOperations}
                />
              )}
              <LiensSuite dossierId={dossierId} />
              {fiche.paie_par_bulletin && <PaieSection dossierId={dossierId} />}
            </>
          )
        )}
      </div>
    </div>
  );
}

/** L'affectation tant qu'elle se décide, puis les dividendes tant que la
 * déclaration n'est pas faite. Les deux liens restent trouvables. */
function LiensSuite({ dossierId }: { dossierId: string }) {
  const [affectation, setAffectation] = useState<AffectationVue | null>(null);
  const [dividendes, setDividendes] = useState<DividendesVue | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [essai, setEssai] = useState(0);

  const charger = useCallback(() => {
    let annule = false;
    Promise.all([
      fetchAvecAuthChauffeur<AffectationVue>(`/dossiers/${dossierId}/affectation`),
      fetchAvecAuthChauffeur<DividendesVue>(`/dossiers/${dossierId}/dividendes`),
    ])
      .then(([affectationVue, dividendesVue]) => {
        if (annule) return;
        setAffectation(affectationVue);
        setDividendes(dividendesVue);
        setErreur(null);
      })
      .catch((exception: unknown) => {
        if (!annule) {
          setErreur(messageVisible(exception, "Impossible de charger la suite de l'exercice."));
        }
      });
    return () => {
      annule = true;
    };
  }, [dossierId]);

  useEffect(() => charger(), [charger, essai]);

  if (erreur) {
    return (
      <EtatErreur
        message={erreur}
        onReessayer={() => {
          setErreur(null);
          setEssai((n) => n + 1);
        }}
      />
    );
  }
  return (
    <div className="mt-8 space-y-3">
      {affectation?.applicable && (
        <Link
          href={`/chauffeur/${dossierId}/resultat`}
          className="block min-h-11 rounded-md border border-border bg-canvas p-3 text-sm text-ink"
        >
          Décider ce que je fais de mon résultat {affectation.annee_exercice} →
        </Link>
      )}
      {dividendes?.applicable && !dividendes.declare && (
        <Link
          href={`/chauffeur/${dossierId}/resultat`}
          className="block min-h-11 rounded-md border border-border bg-canvas p-3 text-sm text-ink"
        >
          Mes dividendes →
        </Link>
      )}
    </div>
  );
}
