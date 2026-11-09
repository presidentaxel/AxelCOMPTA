"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { listerQuarantaine, resoudreQuarantaine } from "@/lib/auth-gestionnaire";
import { formatDate, formatMontant } from "@/lib/format";
import { phraseResolution, resteATraiter, trierQuarantaine } from "@/lib/quarantaine";
import type { EntreeQuarantaine } from "@/lib/types";

/** Opérations bancaires que la synchro n'a pas pu écrire seule (AXE-424) :
 * montant changé ou opération retirée par la banque, opération datée dans
 * un exercice clos. « Accepter » écrit en comptabilité ; « Ignorer » non. */
export function QuarantaineDossier({ dossierId, ecriture }: { dossierId: string; ecriture: boolean }) {
  const [entrees, setEntrees] = useState<EntreeQuarantaine[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState<string | null>(null);

  useEffect(() => {
    listerQuarantaine(dossierId)
      .then(setEntrees)
      .catch(() => setErreur("Impossible de lire les opérations à revoir."));
  }, [dossierId]);

  function resoudre(entree: EntreeQuarantaine, decision: "accepter" | "ignorer") {
    setEnvoi(entree.id);
    setErreur(null);
    resoudreQuarantaine(dossierId, entree.id, decision)
      .then((resolue) =>
        setEntrees((courantes) => (courantes ?? []).map((e) => (e.id === resolue.id ? resolue : e))),
      )
      .catch((exception) => setErreur(exception instanceof Error ? exception.message : "Erreur."))
      .finally(() => setEnvoi(null));
  }

  if (!entrees || entrees.length === 0) {
    return erreur ? <p className="mt-6 text-sm text-danger">{erreur}</p> : null;
  }
  return (
    <section className="mt-8">
      <h2 className="text-lg font-semibold text-ink">
        Opérations bancaires à revoir ({resteATraiter(entrees)})
      </h2>
      {erreur && <p className="mt-2 text-sm text-danger">{erreur}</p>}
      <ul className="mt-3">
        {trierQuarantaine(entrees).map((entree) => {
          const resolution = phraseResolution(entree, formatDate);
          return (
            <li key={entree.id} className="border-b border-hairline py-3">
              <p className="text-sm font-medium text-ink">{entree.libelle_motif}</p>
              <p className="mt-1 flex items-baseline justify-between gap-3 text-sm">
                <span className="min-w-0 truncate text-ink">
                  {entree.date ? `${formatDate(entree.date)} · ` : ""}
                  {entree.libelle ?? "Ligne illisible"}
                </span>
                {entree.montant_cts !== null && (
                  <span className="shrink-0 tabular-nums">{formatMontant(entree.montant_cts)}</span>
                )}
              </p>
              {resolution ? (
                <p className="mt-1 text-xs text-subtle">{resolution}</p>
              ) : (
                ecriture && (
                  <div className="mt-2 flex gap-2">
                    {entree.resoluble && (
                      <Button
                        type="button"
                        size="sm"
                        disabled={envoi === entree.id}
                        onClick={() => resoudre(entree, "accepter")}
                      >
                        Accepter
                      </Button>
                    )}
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={envoi === entree.id}
                      onClick={() => resoudre(entree, "ignorer")}
                    >
                      Ignorer
                    </Button>
                  </div>
                )
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
