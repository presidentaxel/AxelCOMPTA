"use client";

import { useCallback, useEffect, useState } from "react";

import { Etat } from "@/components/Etat";
import { Squelette } from "@/components/Squelette";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatDate, formatMontant } from "@/lib/format";
import {
  correspondanceJson,
  lireDeficits,
  phraseOuverture,
  type AnalyseFec,
  type OuvertureVue,
} from "@/lib/ouverture";

export type ChampsReprise = {
  correspondance: string;
  attestation: string;
  deficits_euros: string;
  motif?: string;
};

type Props = {
  lire: () => Promise<OuvertureVue>;
  analyser: (fichier: File, correspondance: string) => Promise<AnalyseFec>;
  reprendre: (fichier: File, champs: ChampsReprise) => Promise<OuvertureVue>;
  /** L'expert-comptable motive chacun de ses changements (AXE-800). */
  avecMotif?: boolean;
};

function message(exception: unknown, repli: string): string {
  return exception instanceof Error ? exception.message : repli;
}

/** AXE-804 : reprise du bilan d'ouverture d'une société existante depuis le
 * FEC de son outil précédent. Analyse d'abord (rien n'est écrit), puis
 * reprise après attestation. Une seule fois : ensuite, on le dit. */
export function RepriseFec({ lire, analyser, reprendre, avecMotif = false }: Props) {
  const [ouverture, setOuverture] = useState<OuvertureVue | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(() => {
    setErreur(null);
    lire()
      .then(setOuverture)
      .catch((exception: unknown) => setErreur(message(exception, "Impossible de lire le bilan d'ouverture.")));
  }, [lire]);

  useEffect(() => {
    // Premier chargement à l'ouverture de l'écran.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    charger();
  }, [charger]);

  if (erreur) return <Etat type="erreur" message={erreur} onReessayer={charger} />;
  if (!ouverture) {
    return (
      <Etat type="chargement" className="mt-0">
        <Squelette className="h-24 w-full" />
      </Etat>
    );
  }
  if (ouverture.faite) {
    return (
      <p className="mt-4 text-sm text-ink">
        {phraseOuverture(ouverture)} Une correction passe par une écriture d&apos;opérations diverses.
      </p>
    );
  }
  return <Formulaire analyser={analyser} reprendre={reprendre} avecMotif={avecMotif} onFait={setOuverture} />;
}

function Formulaire({
  analyser,
  reprendre,
  avecMotif,
  onFait,
}: Omit<Props, "lire"> & { onFait: (ouverture: OuvertureVue) => void }) {
  const [fichier, setFichier] = useState<File | null>(null);
  const [analyse, setAnalyse] = useState<AnalyseFec | null>(null);
  const [correspondances, setCorrespondances] = useState<Record<string, string>>({});
  const [deficits, setDeficits] = useState("");
  const [motif, setMotif] = useState("");
  const [atteste, setAtteste] = useState(false);
  const [envoi, setEnvoi] = useState(false);
  const [refus, setRefus] = useState<string | null>(null);

  async function lancerAnalyse(choisi: File | null = fichier) {
    if (!choisi) return;
    setEnvoi(true);
    setRefus(null);
    try {
      setAnalyse(await analyser(choisi, correspondanceJson(correspondances)));
      setAtteste(false);
    } catch (exception) {
      setAnalyse(null);
      setRefus(message(exception, "Le fichier n'a pas pu être lu."));
    } finally {
      setEnvoi(false);
    }
  }

  async function valider() {
    const lus = lireDeficits(deficits);
    if (!fichier || !analyse || lus.euros === null) {
      setRefus(lus.message);
      return;
    }
    setEnvoi(true);
    setRefus(null);
    try {
      const champs: ChampsReprise = {
        correspondance: correspondanceJson(correspondances),
        attestation: analyse.attestation,
        deficits_euros: String(lus.euros),
      };
      onFait(await reprendre(fichier, avecMotif ? { ...champs, motif } : champs));
    } catch (exception) {
      setRefus(message(exception, "La reprise a échoué."));
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <div className="mt-4 space-y-4 text-sm text-ink">
      <p className="text-subtle">
        Déposez le FEC de l&apos;exercice précédent, tel que l&apos;outil de l&apos;ancien comptable l&apos;a produit
        (nom en SIRENFECAAAAMMJJ). Rien n&apos;est écrit avant votre validation.
      </p>
      <label className="block">
        Fichier FEC
        <input
          type="file"
          accept=".txt,.csv,text/plain"
          className="mt-1 block w-full text-sm"
          onChange={(e) => {
            const choisi = e.target.files?.[0] ?? null;
            setFichier(choisi);
            void lancerAnalyse(choisi);
          }}
        />
      </label>
      {envoi && <p className="text-subtle">Lecture…</p>}
      {analyse && (
        <Resultat
          analyse={analyse}
          correspondances={correspondances}
          onCorrespondance={(compte, cible) => setCorrespondances({ ...correspondances, [compte]: cible })}
          onReanalyser={() => void lancerAnalyse()}
        />
      )}
      {analyse?.possible && (
        <div className="space-y-3">
          <label className="block">
            Déficits reportables à l&apos;ouverture, en euros (2033-D ligne 870 de l&apos;exercice précédent)
            <Input uiSize="lg" className="mt-1" inputMode="numeric" value={deficits} onChange={(e) => setDeficits(e.target.value)} />
          </label>
          {avecMotif && (
            <label className="block">
              Motif
              <Input uiSize="lg" className="mt-1" value={motif} onChange={(e) => setMotif(e.target.value)} />
            </label>
          )}
          <label className="flex items-start gap-2">
            <input type="checkbox" className="mt-1" checked={atteste} onChange={(e) => setAtteste(e.target.checked)} />
            <span>{analyse.attestation}</span>
          </label>
          <Button type="button" className="h-11 w-full" disabled={!atteste || envoi} onClick={valider}>
            Reprendre ce bilan d&apos;ouverture
          </Button>
        </div>
      )}
      {refus && <p className="text-danger">{refus}</p>}
    </div>
  );
}

function Resultat({
  analyse,
  correspondances,
  onCorrespondance,
  onReanalyser,
}: {
  analyse: AnalyseFec;
  correspondances: Record<string, string>;
  onCorrespondance: (compte: string, cible: string) => void;
  onReanalyser: () => void;
}) {
  return (
    <section aria-label="Analyse du FEC" className="space-y-3">
      <p>
        FEC du SIREN {analyse.siren}, exercice clos le {formatDate(analyse.cloture)} : {analyse.nb_ecritures} écritures.
        Résultat {formatMontant(analyse.resultat_cts)}, capital {formatMontant(analyse.capital_cts)}.
      </p>
      {analyse.refus.length > 0 && (
        <ul className="space-y-1 rounded-md border border-danger-border bg-danger-subtle p-3 text-danger">
          {analyse.refus.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}
      {analyse.comptes_inconnus.length > 0 && (
        <div className="space-y-2">
          <p className="font-medium">Comptes à faire correspondre au plan comptable</p>
          {analyse.comptes_inconnus.map((compte) => (
            <label key={compte} className="block">
              {compte}
              <Input
                className="mt-1"
                inputMode="numeric"
                placeholder="ex. 6061"
                value={correspondances[compte] ?? ""}
                onChange={(e) => onCorrespondance(compte, e.target.value)}
              />
            </label>
          ))}
          <Button type="button" variant="secondary" className="h-11 w-full" onClick={onReanalyser}>
            Relire avec ces correspondances
          </Button>
        </div>
      )}
      {analyse.alertes.length > 0 && (
        <ul className="space-y-1 rounded-md border border-warning-border bg-warning-subtle p-3">
          {analyse.alertes.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
      )}
      {analyse.possible && (
        <table className="w-full text-left tabular-nums">
          <thead>
            <tr className="text-subtle">
              <th className="py-1">Compte</th>
              <th className="py-1 text-right">Débit</th>
              <th className="py-1 text-right">Crédit</th>
            </tr>
          </thead>
          <tbody>
            {analyse.a_nouveaux.map((ligne) => (
              <tr key={ligne.compte} className="border-t border-hairline">
                <td className="py-1">{ligne.compte}</td>
                <td className="py-1 text-right">{ligne.debit_cts ? formatMontant(ligne.debit_cts) : ""}</td>
                <td className="py-1 text-right">{ligne.credit_cts ? formatMontant(ligne.credit_cts) : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
