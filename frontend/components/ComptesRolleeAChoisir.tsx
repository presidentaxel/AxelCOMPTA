"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { choisirCompteRollee } from "@/lib/auth-gestionnaire";
import { apercuCompte, bandeauRollee, type RolleePortefeuille } from "@/lib/liens-rollee";

/** AXE-911 : les comptes Rollee que le rapprochement n'a pas reliés seuls.
 * Les candidats sont classés par force, avec ce qui correspond. Rien en
 * clair : initiales, plateformes, fin d'IBAN (doc 19). */
export function ComptesRolleeAChoisir({
  vue,
  ecriture,
  onChoisi,
}: {
  vue: RolleePortefeuille;
  ecriture: boolean;
  onChoisi: () => void;
}) {
  const [ouvert, setOuvert] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState<string | null>(null);
  const bandeau = bandeauRollee(vue);
  if (!bandeau) return null;

  async function choisir(rolleeUserId: string, dossierId: string | null) {
    setEnvoi(rolleeUserId);
    setErreur(null);
    try {
      await choisirCompteRollee(rolleeUserId, dossierId);
      onChoisi();
    } catch (exception) {
      setErreur(exception instanceof ApiError ? exception.message : "Le choix n'a pas été enregistré.");
    } finally {
      setEnvoi(null);
    }
  }

  return (
    <section
      aria-label="Comptes Rollee à relier"
      className="mt-4 rounded-md border border-warning/40 bg-pending-subtle px-4 py-2.5"
    >
      <div className="flex flex-wrap items-center gap-3">
        <p role="status" className="flex-1 text-sm text-ink">
          {bandeau}
        </p>
        <Button type="button" variant="secondary" size="sm" onClick={() => setOuvert((o) => !o)}>
          {ouvert ? "Masquer" : "Choisir"}
        </Button>
      </div>
      {ouvert && (
        <ul className="mt-3 divide-y divide-hairline">
          {vue.a_choisir.map((compte) => (
            <li key={compte.rollee_user_id} className="py-3">
              <p className="text-sm font-medium text-ink">{apercuCompte(compte)}</p>
              {compte.candidats.length === 0 ? (
                <p className="mt-1 text-sm text-subtle">Aucune entreprise ne correspond.</p>
              ) : (
                <ul className="mt-2 space-y-2">
                  {compte.candidats.map((candidat) => (
                    <li key={candidat.dossier_id} className="flex flex-wrap items-center gap-3">
                      <span className="flex-1 text-sm text-ink">
                        {candidat.nom}
                        <span className="block text-xs text-subtle">{candidat.raisons.join(", ")}</span>
                      </span>
                      {ecriture && (
                        <Button
                          type="button"
                          size="sm"
                          disabled={envoi !== null}
                          onClick={() => void choisir(compte.rollee_user_id, candidat.dossier_id)}
                        >
                          Relier
                        </Button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              {ecriture && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="mt-2"
                  disabled={envoi !== null}
                  onClick={() => void choisir(compte.rollee_user_id, null)}
                >
                  Aucun de ces comptes
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {erreur && <p className="mt-2 text-xs text-danger">{erreur}</p>}
    </section>
  );
}
