"use client";

// Louis, 2026-09-26 : ce que le chauffeur fait de son résultat, c'est lui
// qui le choisit, sur son propre écran. L'API chiffre des scénarios, du
// moins au plus de dividendes, bornés par ce qui est distribuable et par la
// trésorerie ; il retient l'un d'eux ou son propre montant.
import Link from "next/link";
import { use, useEffect, useState } from "react";

import { useDossierChauffeur, type Bloc } from "@/app/chauffeur/use-dossier";
import { Aide } from "@/components/Aide";
import { Button } from "@/components/ui/button";
import { DividendesSection } from "@/components/DividendesSection";
import { ResultatACeJour } from "@/components/ResultatACeJour";
import { Squelette, SqueletteLignes } from "@/components/Squelette";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import {
  ErreurAuthChauffeur,
  deciderAffectationChauffeur,
  fetchAvecAuthChauffeur,
} from "@/lib/auth-chauffeur";
import { formatMontant } from "@/lib/format";
import { phrasePourChauffeur } from "@/lib/langage-chauffeur";
import { lireMontantEuros } from "@/lib/montant";
import type { AffectationVue, DossierResume, ScenarioAffectation } from "@/lib/types";

export default function ResultatChauffeurPage({
  params,
}: {
  params: Promise<{ dossierId: string }>;
}) {
  const { dossierId } = use(params);
  const { dossier } = useDossierChauffeur(dossierId);
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
    <Link
      href={`/chauffeur/${dossierId}/exercice`}
      className="inline-flex min-h-11 items-center text-sm text-subtle underline"
    >
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
        <p className="text-sm text-subtle">{vue.raison && phrasePourChauffeur(vue.raison)}</p>
        <DividendesSection dossierId={dossierId} />
        <div className="mt-4">{retour}</div>
      </div>
    );
  }

  const lecture = lireMontantEuros(montantLibre);
  const dividendes =
    choix === "libre"
      ? lecture.centimes
      : (vue.scenarios.find((scenario) => scenario.cle === choix)?.dividendes_cts ?? null);
  const messageMontant = choix === "libre" ? lecture.message : null;
  const pret = choix !== null && dividendes !== null && confirme;

  async function decider() {
    if (choix === null || dividendes === null) return;
    setEnCours(true);
    setErreur(null);
    try {
      const resultat = await deciderAffectationChauffeur(dossierId, choix, dividendes);
      setFait(
        phrasePourChauffeur(resultat.raison ?? "Décision enregistrée."),
      );
    } catch (exception) {
      setErreur(
        phrasePourChauffeur(
          exception instanceof ErreurAuthChauffeur || exception instanceof ApiError
            ? exception.message
            : "Échec de l'enregistrement.",
        ),
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
      <div className="mt-4">
        <BlocResultat dossier={dossier} />
      </div>
      <dl className="mt-4 space-y-1 text-sm">
        <Ligne
          libelle="Ce qui vous reste après charges"
          cents={vue.resultat_cts}
          aide="C'est le résultat de l'exercice."
        />
        <Ligne
          libelle="À mettre de côté"
          cents={vue.reserve_legale_cts}
          aide="La réserve légale : la loi demande de garder 5 % du bénéfice, jusqu'à 10 % du capital. Vous ne pouvez pas vous la verser."
        />
        <Ligne
          libelle="Ce que vous pouvez vous verser"
          cents={vue.distribuable_cts}
          aide="Le bénéfice distribuable : ce qui reste après cette mise de côté."
        />
        <Ligne
          libelle="Disponible en banque"
          cents={vue.disponible_cts}
          aide="L'argent en banque, une fois retirées les sommes déjà dues."
        />
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
        <ChampMontantLibre
          choisi={choix === "libre"}
          montant={montantLibre}
          message={messageMontant}
          onChoisir={() => setChoix("libre")}
          onMontant={setMontantLibre}
        />
      </ul>
      <ul className="mt-4 space-y-1 text-xs text-subtle">
        {vue.avertissements.map((avertissement) => (
          <li key={avertissement}>{avertissement}</li>
        ))}
      </ul>
      <label className="mt-4 flex min-h-11 gap-3 text-base text-ink">
        <input
          type="checkbox"
          className="mt-0.5 size-6 shrink-0"
          checked={confirme}
          onChange={(evenement) => setConfirme(evenement.target.checked)}
        />
        <span>
          Je décide de cette répartition, en tant que seul associé. AxeLCompta a chiffré les
          scénarios ; le choix est le mien.
        </span>
      </label>
      <Button className="mt-3 h-11" disabled={!pret || enCours} onClick={decider}>
        {enCours ? "Enregistrement…" : "Enregistrer ma décision"}
      </Button>
      {erreur && <p className="mt-2 text-sm text-danger">{erreur}</p>}
      <div className="mt-6">{retour}</div>
    </div>
  );
}

function BlocResultat({ dossier }: { dossier: Bloc<DossierResume> }) {
  if (dossier.statut === "en_cours") {
    return (
      <div>
        <Squelette className="h-8 w-32" />
        <Squelette className="mt-2 h-4 w-56" />
      </div>
    );
  }
  if (dossier.statut === "erreur") {
    return <p className="text-sm text-danger">{dossier.message}</p>;
  }
  return <ResultatACeJour dossier={dossier.valeur} />;
}

function ChampMontantLibre({
  choisi,
  montant,
  message,
  onChoisir,
  onMontant,
}: {
  choisi: boolean;
  montant: string;
  message: string | null;
  onChoisir: () => void;
  onMontant: (valeur: string) => void;
}) {
  return (
    <li className={`rounded-md border bg-canvas p-3 text-base ${choisi ? "border-ink" : "border-border"}`}>
      <div className="flex min-h-11 items-center gap-3 text-sm">
        <input
          id="scenario-libre"
          type="radio"
          name="scenario"
          value="libre"
          className="size-6 shrink-0"
          checked={choisi}
          onChange={onChoisir}
        />
        <label htmlFor="scenario-libre" className="text-ink">
          Un autre montant de dividendes
        </label>
      </div>
      <div className="mt-3 pl-7">
        <label htmlFor="montant-dividendes" className="mb-1 block text-sm font-medium text-ink">
          Montant (€)
        </label>
        <Input
          id="montant-dividendes"
          name="montant-dividendes"
          uiSize="lg"
          inputMode="decimal"
          value={montant}
          aria-invalid={message !== null}
          aria-describedby={message ? "montant-dividendes-message" : undefined}
          onFocus={onChoisir}
          onChange={(evenement) => onMontant(evenement.target.value)}
        />
        {message && (
          <p id="montant-dividendes-message" role="alert" className="mt-1 text-sm text-danger">
            {message}
          </p>
        )}
      </div>
    </li>
  );
}

function Ligne({ libelle, cents, aide }: { libelle: string; cents: number; aide?: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-subtle">
        {libelle}
        {aide && <Aide texte={aide} />}
      </dt>
      <dd className="shrink-0 tabular-nums text-ink">{formatMontant(cents)}</dd>
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
        <span className="flex min-h-11 items-center gap-3">
          <input
            type="radio"
            name="scenario"
            value={scenario.cle}
            className="size-6 shrink-0"
            checked={choisi}
            onChange={onChoisir}
          />
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
