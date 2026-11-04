"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  annulerImputation,
  ErreurAuthGestionnaire,
  imputerExpert,
  lireFileExpert,
} from "@/lib/auth-gestionnaire";
import { formatMontant } from "@/lib/format";
import type { FileExpert, ImputationFaite, SujetExpert } from "@/lib/types";

const COTE: Record<SujetExpert["cote"], string> = {
  chauffeur: "À traiter par l'entreprise",
  gestionnaire: "À traiter par le gestionnaire",
};
const NATURE: Record<SujetExpert["nature"], string> = {
  a_trancher: "Opération",
  ticket: "Ticket",
  anomalie: "Anomalie",
};
const SENS = { debit: "Débit", credit: "Crédit" } as const;

/** L'imputation écrit dans la comptabilité : on le dit, on montre les lignes,
 * et on peut contre-passer. */
export default function ModeExpertPage() {
  const router = useRouter();
  const [file, setFile] = useState<FileExpert | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [erreurs, setErreurs] = useState<Record<string, string>>({});
  const [compte, setCompte] = useState<Record<string, string>>({});
  const [enCours, setEnCours] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<SujetExpert | null>(null);
  const [succes, setSucces] = useState<{
    dossierId: string;
    libelle: string;
    imputation: ImputationFaite;
  } | null>(null);

  const charger = useCallback(() => {
    lireFileExpert()
      .then((donnees) => {
        setFile(donnees);
        setCompte((actuel) => {
          const suite = { ...actuel };
          for (const sujet of donnees.sujets) {
            if (!suite[sujet.id] && sujet.compte_suggere) suite[sujet.id] = sujet.compte_suggere;
          }
          return suite;
        });
      })
      .catch((exception) => {
        if (exception instanceof ErreurAuthGestionnaire) {
          router.replace("/connexion");
        } else {
          setErreur("Impossible de charger la file.");
        }
      });
  }, [router]);

  useEffect(charger, [charger]);

  async function imputer(sujet: SujetExpert) {
    const choisi = compte[sujet.id];
    if (!choisi || !sujet.ecriture_id) return;
    setEnCours(sujet.id);
    setConfirmation(null);
    setErreurs((actuel) => {
      const suite = { ...actuel };
      delete suite[sujet.id];
      return suite;
    });
    try {
      const imputation = await imputerExpert(sujet.dossier_id, sujet.ecriture_id, choisi);
      setSucces({ dossierId: sujet.dossier_id, libelle: sujet.libelle, imputation });
      charger();
    } catch (exception) {
      if (exception instanceof ErreurAuthGestionnaire) {
        router.replace("/connexion");
        return;
      }
      setErreurs((actuel) => ({
        ...actuel,
        [sujet.id]: exception instanceof Error ? exception.message : "Échec de l'imputation.",
      }));
    } finally {
      setEnCours(null);
    }
  }

  async function annuler() {
    if (!succes) return;
    setEnCours("annuler");
    try {
      await annulerImputation(
        succes.dossierId,
        succes.imputation.ecriture_id,
        succes.imputation.contrepassation_id,
      );
      setSucces(null);
      charger();
    } catch (exception) {
      if (exception instanceof ErreurAuthGestionnaire) {
        router.replace("/connexion");
        return;
      }
      setErreur(exception instanceof Error ? exception.message : "Échec de l'annulation.");
    } finally {
      setEnCours(null);
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-[28px] font-bold tracking-tight text-ink">Mode expert</h1>
      <p className="mt-2 text-sm text-subtle">
        Libellés et montants des écritures encore ouvertes. « Imputer » écrit dans la
        comptabilité de l&apos;entreprise : une contre-passation, puis une nouvelle écriture.
        Le tableau de bord du portefeuille, lui, ne change pas.
      </p>
      {erreur && <p className="mt-6 text-sm text-danger">{erreur}</p>}
      {succes && (
        <div className="mt-6 rounded-lg border border-border bg-canvas p-4">
          <p className="text-sm font-medium text-ink">Écrit pour {succes.libelle}</p>
          <ul className="mt-2 space-y-1">
            {succes.imputation.lignes.map((ligne, index) => (
              <li key={`${ligne.compte}-${index}`} className="text-sm text-ink">
                {SENS[ligne.sens]} {ligne.compte}
                <span className="ml-2 tabular-nums text-subtle">{formatMontant(ligne.montant_cts)}</span>
              </li>
            ))}
          </ul>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="mt-3"
            disabled={enCours === "annuler"}
            onClick={() => void annuler()}
          >
            Annuler
          </Button>
        </div>
      )}
      {!file && !erreur && <p className="mt-8 text-sm text-subtle">Chargement…</p>}
      {file && file.sujets.length === 0 && (
        <p className="mt-8 text-sm text-subtle">Rien en attente.</p>
      )}
      <ul className="mt-6">
        {file?.sujets.map((sujet) => (
          <li key={sujet.id} className="border-b border-hairline py-4">
            <div className="flex items-baseline justify-between gap-4">
              <p className="min-w-0">
                <span className="block truncate text-base font-semibold text-ink">{sujet.libelle}</span>
                <span className="mt-0.5 block text-sm text-subtle">
                  {sujet.dossier_nom} · {COTE[sujet.cote]} · {NATURE[sujet.nature]}
                </span>
                <span className="mt-0.5 block text-sm text-subtle">{sujet.detail}</span>
                {sujet.compte_actuel && (
                  <span className="mt-0.5 block text-sm text-subtle">
                    Compte actuel {sujet.compte_actuel}
                    {sujet.compte_suggere ? ` · suggéré ${sujet.compte_suggere}` : ""}
                  </span>
                )}
              </p>
              {sujet.montant_cts !== null && (
                <span
                  className={`shrink-0 text-base font-semibold tabular-nums ${
                    sujet.montant_cts < 0 ? "text-amount-negative" : "text-amount-positive"
                  }`}
                >
                  {formatMontant(sujet.montant_cts)}
                </span>
              )}
            </div>
            {sujet.nature === "anomalie" && (
              <Link
                href={`/anomalies/${sujet.dossier_id}`}
                className="mt-3 inline-block text-sm font-medium text-primary hover:underline"
              >
                Instruire
              </Link>
            )}
            {sujet.nature !== "anomalie" && sujet.imputable && sujet.ecriture_id && file && (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <select
                  aria-label={`Compte pour ${sujet.libelle}`}
                  value={compte[sujet.id] ?? ""}
                  onChange={(evenement) =>
                    setCompte((actuel) => ({ ...actuel, [sujet.id]: evenement.target.value }))
                  }
                  className="h-9 min-w-56 rounded-md border border-border bg-canvas px-3 text-sm text-ink"
                >
                  <option value="">Compte</option>
                  {file.comptes.map((choix) => (
                    <option key={choix.compte} value={choix.compte}>
                      {choix.compte} — {choix.libelle}
                    </option>
                  ))}
                </select>
                <Button
                  type="button"
                  size="sm"
                  disabled={!compte[sujet.id] || enCours === sujet.id}
                  onClick={() => setConfirmation(sujet)}
                >
                  Imputer
                </Button>
                {sujet.nature === "ticket" && (
                  <span className="text-xs text-subtle">Écrit en comptabilité sans le ticket.</span>
                )}
              </div>
            )}
            {erreurs[sujet.id] && <p className="mt-2 text-sm text-danger">{erreurs[sujet.id]}</p>}
            {confirmation?.id === sujet.id && (
              <div className="mt-3 rounded-lg border border-border bg-canvas-app p-4">
                <p className="text-sm text-ink">
                  Écrire dans la comptabilité de {sujet.dossier_nom} : le compte {compte[sujet.id]}{" "}
                  remplace la contrepartie, le compte 512 reste. Les lignes Débit et Crédit
                  s&apos;affichent ensuite, et l&apos;écriture se défait.
                </p>
                <div className="mt-3 flex justify-end gap-2">
                  <Button type="button" variant="ghost" size="sm" onClick={() => setConfirmation(null)}>
                    Annuler
                  </Button>
                  <Button type="button" size="sm" disabled={enCours === sujet.id} onClick={() => void imputer(sujet)}>
                    Écrire
                  </Button>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
