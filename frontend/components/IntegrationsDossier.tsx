"use client";

import { useEffect, useState } from "react";

import {
  choisirBranchementDossier,
  lireBranchementsDossier,
  listerBranchements,
  type Branchement,
} from "@/lib/auth-gestionnaire";
import { ORDRE_TYPES, TYPES_BRANCHEMENT } from "@/lib/branchements";

/** AXE-872 : l'accès qu'une entreprise utilise, pour chaque intégration qui
 * en a plusieurs. Rien à choisir quand il n'y en a qu'un : ce bloc n'apparaît pas. */
export function IntegrationsDossier({
  dossierId,
  admin,
}: {
  dossierId: string;
  admin: boolean;
}) {
  const [branchements, setBranchements] = useState<Branchement[]>([]);
  const [choix, setChoix] = useState<Record<string, string>>({});
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    let actif = true;
    Promise.all([listerBranchements(), lireBranchementsDossier(dossierId)])
      .then(([liste, lus]) => {
        if (!actif) return;
        setBranchements(liste);
        setChoix(lus);
      })
      .catch(() => {
        // Non lus : le bloc reste caché, l'entreprise garde les accès par défaut.
      });
    return () => {
      actif = false;
    };
  }, [dossierId]);

  const types = ORDRE_TYPES.filter(
    (type) => branchements.filter((b) => b.type === type && b.actif).length > 1,
  );
  if (types.length === 0) return null;

  return (
    <div className="mt-8">
      <p className="text-sm font-medium text-ink">Intégrations utilisées</p>
      <dl className="mt-2 space-y-2">
        {types.map((type) => {
          const actifs = branchements.filter((b) => b.type === type && b.actif);
          const sansDefaut = type === "rollee";
          const defaut = actifs.find((b) => b.par_defaut);
          return (
            <div key={type} className="flex items-center justify-between gap-4">
              <dt className="text-sm text-subtle">
                {TYPES_BRANCHEMENT[type].nom}
              </dt>
              <dd>
                <select
                  aria-label={`Accès ${TYPES_BRANCHEMENT[type].nom} de cette entreprise`}
                  disabled={!admin}
                  value={choix[type] ?? ""}
                  onChange={async (evenement) => {
                    setErreur(null);
                    try {
                      setChoix(
                        await choisirBranchementDossier(
                          dossierId,
                          type,
                          evenement.target.value || null,
                        ),
                      );
                    } catch (exception) {
                      setErreur(
                        exception instanceof Error
                          ? exception.message
                          : "Choix non enregistré.",
                      );
                    }
                  }}
                  className="rounded-md border border-border bg-canvas px-2 py-1 text-sm text-ink"
                >
                  <option value="">
                    {sansDefaut
                      ? "Pas encore relié, on interroge tous"
                      : `Par défaut${defaut ? ` (${defaut.nom})` : ""}`}
                  </option>
                  {actifs
                    .filter((b) => sansDefaut || !b.par_defaut)
                    .map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.nom}
                      </option>
                    ))}
                </select>
              </dd>
            </div>
          );
        })}
      </dl>
      {erreur && <p className="mt-2 text-sm text-danger">{erreur}</p>}
    </div>
  );
}
