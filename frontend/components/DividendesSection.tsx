"use client";

// Après l'affectation : le chauffeur verse ses dividendes et le déclare ici.
// La société retient à la source le prélèvement forfaitaire (sauf dispense)
// et les prélèvements sociaux, et les reverse avec la déclaration 2777 avant
// le 15 du mois suivant. Le virement net et le paiement de la 2777 se
// catégorisent ensuite depuis la banque.
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import {
  ErreurAuthChauffeur,
  declarerDividendesChauffeur,
  fetchAvecAuthChauffeur,
} from "@/lib/auth-chauffeur";
import { formatDate, formatMontant } from "@/lib/format";
import type { DividendesVue } from "@/lib/types";

export function DividendesSection({ dossierId }: { dossierId: string }) {
  const [vue, setVue] = useState<DividendesVue | null>(null);
  const [verseLe, setVerseLe] = useState(() => new Date().toISOString().slice(0, 10));
  const [dispense, setDispense] = useState(false);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    fetchAvecAuthChauffeur<DividendesVue>(`/dossiers/${dossierId}/dividendes`)
      .then(setVue)
      .catch(() => setVue(null));
  }, [dossierId]);

  if (!vue?.applicable) {
    return null;
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
        <Ligne libelle="Dividendes décidés" cents={vue.brut_cts} />
        <Ligne libelle="Prélèvement forfaitaire (12,8 %)" cents={vue.prelevement_forfaitaire_cts} />
        <Ligne libelle="CSG" cents={vue.csg_cts} />
        <Ligne libelle="CRDS" cents={vue.crds_cts} />
        <Ligne libelle="Prélèvement de solidarité" cents={vue.solidarite_cts} />
        <Ligne libelle="Net à vous virer" cents={vue.net_a_virer_cts} />
      </dl>
      {vue.declare ? (
        <p className="mt-4 rounded-md border border-border bg-canvas p-3 text-sm text-ink">
          Versés le {vue.verse_le && formatDate(vue.verse_le)}. Déclaration 2777 à déposer et
          payer avant le {vue.echeance_2777 && formatDate(vue.echeance_2777)} :{" "}
          {formatMontant(vue.total_retenu_cts)}. Catégorisez ensuite votre virement comme « Mes
          dividendes » et ce paiement comme « Impôts sur mes dividendes ».
        </p>
      ) : (
        <div className="mt-4 space-y-3 text-sm">
          <label className="flex min-h-11 flex-col gap-2">
            <span className="text-subtle">Date du versement</span>
            <Input
              type="date"
              className="h-11 text-base"
              value={verseLe}
              onChange={(evenement) => setVerseLe(evenement.target.value)}
            />
          </label>
          <label className="flex min-h-11 items-start gap-3 text-ink">
            <input
              type="checkbox"
              className="mt-0.5 size-6 shrink-0"
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

function Ligne({ libelle, cents }: { libelle: string; cents: number }) {
  return (
    <div className="flex justify-between">
      <dt className="text-subtle">{libelle}</dt>
      <dd className="tabular-nums text-ink">{formatMontant(cents)}</dd>
    </div>
  );
}
