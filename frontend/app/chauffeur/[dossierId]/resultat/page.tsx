"use client";

// Louis, 2026-09-26 : ce que le chauffeur fait de son résultat, c'est lui
// qui le choisit, sur son propre écran. L'API chiffre des scénarios, du
// moins au plus de dividendes, bornés par ce qui est distribuable et par la
// trésorerie ; il retient l'un d'eux ou son propre montant.
import Link from "next/link";
import { use, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { DividendesSection } from "@/components/DividendesSection";
import { Squelette, SqueletteLignes } from "@/components/Squelette";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import {
  ErreurAuthChauffeur,
  deciderAffectationChauffeur,
  fetchAvecAuthChauffeur,
} from "@/lib/auth-chauffeur";
import { formatMontant } from "@/lib/format";
import type { AffectationVue, ScenarioAffectation } from "@/lib/types";

export default function ResultatChauffeurPage({
  params,
}: {
  params: Promise<{ dossierId: string }>;
}) {
  const { dossierId } = use(params);
  const [vue, setVue] = useState<AffectationVue | null>(null);
  const [choix, setChoix] = useState<string | null>(null);
  const [montantLibre, setMontantLibre] = useState("");
  const [confirme, setConfirme] = useState(false);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [fait, setFait] = useState<string | null>(null);

  useEffect(() => {
    fetchAvecAuthChauffeur<AffectationVue>(`/dossiers/${dossierId}/affectation`)
      .then(setVue)
      .catch(() => setErreur("Impossible de charger votre résultat."));
  }, [dossierId]);

  const retour = (
    <Link href={`/chauffeur/${dossierId}/exercice`} className="text-sm text-subtle underline">
      Retour à l&apos;exercice
    </Link>
  );
  if (fait) {
    return (
      <div>
        <p className="text-sm text-ink">{fait}</p>
        <DividendesSection dossierId={dossierId} />
        <div className="mt-4">{retour}</div>
      </div>
    );
  }
  if (vue === null && erreur) {
    return (
      <div>
        <p className="text-sm text-danger">{erreur}</p>
        <div className="mt-4">{retour}</div>
      </div>
    );
  }
  if (vue === null) {
    return (
      <div>
        <Squelette className="h-8 w-40" />
        <SqueletteLignes nombre={4} className="h-5 w-full" />
        <Squelette className="mt-8 h-24 w-full" />
        <div className="mt-4">{retour}</div>
      </div>
    );
  }
  if (!vue.applicable) {
    return (
      <div>
        <p className="text-sm text-subtle">{vue.raison}</p>
        <DividendesSection dossierId={dossierId} />
        <div className="mt-4">{retour}</div>
      </div>
    );
  }

  const libreCts = Math.round(Number(montantLibre.replace(",", ".")) * 100);
  const dividendes =
    choix === "libre"
      ? libreCts
      : (vue.scenarios.find((scenario) => scenario.cle === choix)?.dividendes_cts ?? null);
  const pret = choix !== null && dividendes !== null && !Number.isNaN(dividendes) && confirme;

  async function decider() {
    if (choix === null || dividendes === null) return;
    setEnCours(true);
    setErreur(null);
    try {
      const resultat = await deciderAffectationChauffeur(dossierId, choix, dividendes);
      setFait(resultat.raison ?? "Décision enregistrée.");
    } catch (exception) {
      setErreur(
        exception instanceof ErreurAuthChauffeur || exception instanceof ApiError
          ? exception.message
          : "Échec de l'enregistrement.",
      );
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div>
      <h1 className="text-[28px] font-bold tracking-tight text-ink">
        Mon résultat {vue.annee_exercice}
      </h1>
      <dl className="mt-4 space-y-1 text-sm">
        <Ligne libelle="Résultat" cents={vue.resultat_cts} />
        <Ligne libelle="Réserve légale à doter" cents={vue.reserve_legale_cts} />
        <Ligne libelle="Distribuable" cents={vue.distribuable_cts} />
        <Ligne libelle="Trésorerie disponible" cents={vue.disponible_cts} />
      </dl>
      <h2 className="mt-8 text-sm font-medium text-ink">Que voulez-vous en faire ?</h2>
      <ul className="mt-3 space-y-2">
        {vue.scenarios.map((scenario) => (
          <CarteScenario
            key={scenario.cle}
            scenario={scenario}
            choisi={choix === scenario.cle}
            onChoisir={() => setChoix(scenario.cle)}
          />
        ))}
        <li>
          <label className="flex items-center gap-3 rounded-md border border-border bg-canvas p-3 text-sm">
            <input type="radio" checked={choix === "libre"} onChange={() => setChoix("libre")} />
            <span className="flex-1 text-ink">Un autre montant de dividendes</span>
            <Input
              inputMode="decimal"
              className="h-8 w-28"
              placeholder="€"
              value={montantLibre}
              onFocus={() => setChoix("libre")}
              onChange={(evenement) => setMontantLibre(evenement.target.value)}
            />
          </label>
        </li>
      </ul>
      <ul className="mt-4 space-y-1 text-xs text-subtle">
        {vue.avertissements.map((avertissement) => (
          <li key={avertissement}>{avertissement}</li>
        ))}
      </ul>
      <label className="mt-4 flex gap-3 text-sm text-ink">
        <input
          type="checkbox"
          className="mt-1"
          checked={confirme}
          onChange={(evenement) => setConfirme(evenement.target.checked)}
        />
        <span>
          Je décide de cette affectation en tant qu&apos;associé unique. AxeLCompta a chiffré les
          scénarios ; le choix est le mien.
        </span>
      </label>
      <Button className="mt-3" disabled={!pret || enCours} onClick={decider}>
        {enCours ? "Enregistrement…" : "Enregistrer ma décision"}
      </Button>
      {erreur && <p className="mt-2 text-sm text-danger">{erreur}</p>}
      <div className="mt-6">{retour}</div>
    </div>
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

function CarteScenario({
  scenario,
  choisi,
  onChoisir,
}: {
  scenario: ScenarioAffectation;
  choisi: boolean;
  onChoisir: () => void;
}) {
  return (
    <li>
      <label
        className={`block rounded-md border p-3 text-sm ${
          choisi ? "border-ink bg-canvas" : "border-border bg-canvas"
        }`}
      >
        <span className="flex items-center gap-3">
          <input type="radio" checked={choisi} onChange={onChoisir} />
          <span className="flex-1 font-medium text-ink">{scenario.libelle}</span>
          <span className="tabular-nums text-ink">{formatMontant(scenario.dividendes_cts)}</span>
        </span>
        {scenario.dividendes_cts > 0 && (
          <span className="mt-2 block space-y-0.5 pl-7 text-xs text-subtle">
            <span className="block">
              Impôt {formatMontant(scenario.impot_revenu_cts)} · prélèvements sociaux{" "}
              {formatMontant(scenario.prelevements_sociaux_cts)} · net perçu{" "}
              {formatMontant(scenario.net_percu_cts)}
            </span>
            {scenario.part_soumise_cotisations_cts > 0 && (
              <span className="block">
                Dont {formatMontant(scenario.part_soumise_cotisations_cts)} soumis à cotisations
                sociales (non chiffrées)
              </span>
            )}
          </span>
        )}
        <span className="mt-1 block pl-7 text-xs text-subtle">
          Reste en société {formatMontant(scenario.laisse_en_societe_cts)} · trésorerie après{" "}
          {formatMontant(scenario.tresorerie_apres_cts)}
        </span>
      </label>
    </li>
  );
}
