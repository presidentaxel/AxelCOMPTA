"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  ErreurAuthGestionnaire,
  imputerExpert,
  lireFileExpert,
} from "@/lib/auth-gestionnaire";
import { formatMontant } from "@/lib/format";
import type { FileExpert, SujetExpert } from "@/lib/types";

const COTE: Record<SujetExpert["cote"], string> = {
  chauffeur: "Chauffeur",
  gestionnaire: "Gestionnaire",
};
const NATURE: Record<SujetExpert["nature"], string> = {
  a_trancher: "À trancher",
  ticket: "Ticket",
  anomalie: "Anomalie",
};

/** File à part du portefeuille : tout ce qui reste à traiter, et l'imputation
 * par l'expert. Le portefeuille agrégé n'est pas modifié. */
export default function ModeExpertPage() {
  const router = useRouter();
  const [file, setFile] = useState<FileExpert | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [compte, setCompte] = useState<Record<string, string>>({});
  const [enCours, setEnCours] = useState<string | null>(null);

  const charger = useCallback(() => {
    lireFileExpert()
      .then(setFile)
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
    setErreur(null);
    try {
      await imputerExpert(sujet.dossier_id, sujet.ecriture_id, choisi);
      charger();
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Échec de l'imputation.");
    } finally {
      setEnCours(null);
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-[28px] font-bold tracking-tight text-ink">Mode expert</h1>
      <p className="mt-2 text-sm text-subtle">
        Tout ce qui reste à traiter, chauffeurs et dossiers confondus. Le portefeuille
        des entreprises ne change pas.
      </p>
      {erreur && <p className="mt-6 text-sm text-danger">{erreur}</p>}
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
            {sujet.imputable && sujet.ecriture_id && file && (
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
                  onClick={() => void imputer(sujet)}
                >
                  Imputer
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
