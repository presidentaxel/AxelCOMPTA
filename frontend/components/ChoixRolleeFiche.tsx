"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { choisirCompteRollee } from "@/lib/auth-gestionnaire";
import { apercuCompte, type AChoisirRollee } from "@/lib/liens-rollee";

/** Le compte Rollee trouvé pour cette entreprise, à relier depuis sa fiche.
 * Rien en clair : initiales, plateformes, fin d'IBAN (doc 19). */
export function ChoixRolleeFiche({
  dossierId,
  comptes,
  ecriture,
  onChoisi,
}: {
  dossierId: string;
  comptes: AChoisirRollee[];
  ecriture: boolean;
  onChoisi: () => void;
}) {
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState<string | null>(null);
  if (comptes.length === 0) return null;

  async function choisir(rolleeUserId: string, retenu: string | null) {
    setEnvoi(rolleeUserId);
    setErreur(null);
    try {
      await choisirCompteRollee(rolleeUserId, retenu);
      onChoisi();
    } catch (exception) {
      setErreur(exception instanceof ApiError ? exception.message : "Le choix n'a pas été enregistré.");
    } finally {
      setEnvoi(null);
    }
  }

  return (
    <section aria-label="Compte Rollee à relier" className="mt-3">
      <p className="text-sm text-ink">
        {comptes.length === 1
          ? "Un compte Rollee correspond à cette entreprise."
          : `${comptes.length} comptes Rollee correspondent à cette entreprise.`}
      </p>
      <ul className="mt-2 space-y-3">
        {comptes.map((compte) => {
          const raisons =
            compte.candidats.find((candidat) => candidat.dossier_id === dossierId)?.raisons ?? [];
          return (
            <li key={compte.rollee_user_id}>
              <p className="text-sm font-medium text-ink">{apercuCompte(compte)}</p>
              {raisons.length > 0 && <p className="text-xs text-subtle">{raisons.join(", ")}</p>}
              {ecriture && (
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    disabled={envoi !== null}
                    onClick={() => void choisir(compte.rollee_user_id, dossierId)}
                  >
                    Relier
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={envoi !== null}
                    onClick={() => void choisir(compte.rollee_user_id, null)}
                  >
                    {"Ce n'est pas lui"}
                  </Button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {erreur && <p className="mt-2 text-xs text-danger">{erreur}</p>}
    </section>
  );
}
