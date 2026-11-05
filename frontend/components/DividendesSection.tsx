"use client";

// Après l'affectation : le chauffeur verse ses dividendes et le déclare ici.
// La société retient à la source le prélèvement forfaitaire (sauf dispense)
// et les prélèvements sociaux, et les reverse avec la déclaration 2777 avant
// le 15 du mois suivant. Le virement net et le paiement de la 2777 se
// catégorisent ensuite depuis la banque.
import { useCallback, useEffect, useState } from "react";

import { Aide } from "@/components/Aide";
import { EtatErreur } from "@/components/EtatChargement";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import {
  ErreurAuthChauffeur,
  declarerDividendesChauffeur,
  fetchAvecAuthChauffeur,
} from "@/lib/auth-chauffeur";
import { formatDate, formatMontant } from "@/lib/format";
import { messageVisible } from "@/lib/messages";
import type { DividendesVue } from "@/lib/types";

export function DividendesSection({ dossierId }: { dossierId: string }) {
  const [vue, setVue] = useState<DividendesVue | null>(null);
  const [echec, setEchec] = useState<string | null>(null);
  const [verseLe, setVerseLe] = useState(() => new Date().toISOString().slice(0, 10));
  const [dispense, setDispense] = useState(false);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(() => {
    let annule = false;
    fetchAvecAuthChauffeur<DividendesVue>(`/dossiers/${dossierId}/dividendes`)
      .then((valeur) => {
        if (annule) return;
        setVue(valeur);
        setEchec(null);
      })
      .catch((exception: unknown) => {
        if (!annule) setEchec(messageVisible(exception, "Impossible de charger vos dividendes."));
      });
    return () => {
      annule = true;
    };
  }, [dossierId]);

  useEffect(() => charger(), [charger]);

  if (echec) {
    return (
      <EtatErreur
        message={echec}
        onReessayer={() => {
          setEchec(null);
          charger();
        }}
      />
    );
  }
  if (vue === null) {
    return null;
  }
  if (!vue.applicable) {
    return vue.raison ? <p className="mt-8 text-sm text-subtle">{vue.raison}</p> : null;
  }

  async function declarer() {
    setEnCours(true);
    setErreur(null);
    try {
      setVue(await declarerDividendesChauffeur(dossierId, verseLe, dispense));
    } catch (exception) {
      setErreur(
        exception instanceof ErreurAuthChauffeur || exception instanceof ApiError
          ? exception.message
          : "Échec de la déclaration.",
      );
    } finally {
      setEnCours(false);
    }
  }

  return (
    <section className="mt-8">
      <h2 className="text-sm font-medium text-ink">Mes dividendes {vue.annee_exercice}</h2>
      <dl className="mt-3 space-y-1 text-sm">
        <Ligne libelle="Montant décidé" cents={vue.brut_cts} />
        <Ligne
          libelle="Impôt retenu (12,8 %)"
          aide="Le prélèvement forfaitaire. Il est retenu par la société avant de vous virer le reste."
          cents={vue.prelevement_forfaitaire_cts}
        />
        <Ligne
          libelle="Cotisations sociales"
          aide="CSG, CRDS et prélèvement de solidarité, retenus en même temps."
          cents={vue.csg_cts + vue.crds_cts + vue.solidarite_cts}
        />
        <Ligne libelle="Ce que vous recevez" cents={vue.net_a_virer_cts} />
      </dl>
      {vue.declare ? (
        <p className="mt-4 rounded-md border border-border bg-canvas p-3 text-sm text-ink">
          Versés le {vue.verse_le && formatDate(vue.verse_le)}. Déclarez et payez{" "}
          {formatMontant(vue.total_retenu_cts)} avant le{" "}
          {vue.echeance_2777 && formatDate(vue.echeance_2777)}
          <Aide
            tactile
            texte="La déclaration 2777 : c'est elle qui dit à l'administration ce qui a été retenu sur vos dividendes."
          />
          . Ensuite, classez votre virement en « Mes dividendes » et ce paiement en « Impôts sur
          mes dividendes ».
        </p>
      ) : (
        <div className="mt-4 space-y-3 text-sm">
          <label className="flex items-center gap-3">
            <span className="text-subtle">Date du versement</span>
            <Input
              type="date"
              uiSize="lg"
              className="w-44"
              aria-label="Date du versement"
              value={verseLe}
              onChange={(evenement) => setVerseLe(evenement.target.value)}
            />
          </label>
          <label className="flex gap-3 text-ink">
            <input
              type="checkbox"
              className="mt-1"
              checked={dispense}
              onChange={(evenement) => setDispense(evenement.target.checked)}
            />
            <span>
              J&apos;ai demandé la dispense du prélèvement forfaitaire avant le 30 novembre de
              l&apos;an dernier (revenu fiscal de référence sous le seuil). Les prélèvements
              sociaux restent dus.
            </span>
          </label>
          <Button className="h-11" disabled={enCours} onClick={declarer}>
            {enCours ? "Déclaration…" : "J'ai versé mes dividendes"}
          </Button>
          {erreur && <p className="text-sm text-danger">{erreur}</p>}
        </div>
      )}
    </section>
  );
}

function Ligne({ libelle, cents, aide }: { libelle: string; cents: number; aide?: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-subtle">
        {libelle}
        {aide && <Aide tactile texte={aide} />}
      </dt>
      <dd className="text-right tabular-nums text-ink">{formatMontant(cents)}</dd>
    </div>
  );
}
