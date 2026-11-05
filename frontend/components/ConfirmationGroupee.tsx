"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { trancherEnGroupeChauffeur } from "@/lib/auth-chauffeur";
import { formatMontant } from "@/lib/format";

/** « Tout confirmer » : des opérations qui ressemblent à ce que le chauffeur a
 * déjà classé lui-même. Il voit la liste avant de confirmer ; l'API écrit
 * toutes les décisions ou aucune. */
export function ConfirmationGroupee({
  dossierId,
  categorie,
  libelle,
  operations,
  onConfirme,
}: {
  dossierId: string;
  categorie: string;
  libelle: string;
  operations: { ecritureId: string; nom: string; montantCts: number }[];
  onConfirme: (ids: string[]) => void;
}) {
  const [ouvert, setOuvert] = useState(false);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  async function confirmer() {
    setEnCours(true);
    setErreur(null);
    try {
      await trancherEnGroupeChauffeur(
        dossierId,
        operations.map((operation) => operation.ecritureId),
        categorie,
      );
      onConfirme(operations.map((operation) => operation.ecritureId));
    } catch (exception) {
      setErreur(exception instanceof ApiError ? exception.message : "Échec de l'envoi.");
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div className="mt-4 rounded-md border border-hairline p-3">
      <p className="text-sm text-ink">
        {operations.length} opérations ressemblent à celles que vous avez classées en «{" "}
        {libelle} ».
      </p>
      {ouvert && (
        <ul className="mt-2 max-h-64 overflow-y-auto text-xs text-subtle">
          {operations.map((operation) => (
            <li key={operation.ecritureId} className="flex justify-between gap-3 py-1">
              <span className="min-w-0 truncate">{operation.nom}</span>
              <span className="shrink-0 tabular-nums">{formatMontant(operation.montantCts)}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex flex-col gap-2">
        <Button
          type="button"
          variant="secondary"
          className="h-11 w-full"
          disabled={enCours}
          onClick={() => setOuvert(!ouvert)}
        >
          {ouvert ? "Masquer la liste" : "Voir la liste"}
        </Button>
        <Button
          type="button"
          className="h-auto min-h-11 w-full px-3 whitespace-normal!"
          disabled={enCours}
          onClick={() => void confirmer()}
        >
          {enCours ? "Envoi…" : `Tout classer en « ${libelle} »`}
        </Button>
      </div>
      {erreur && <p className="mt-1 text-xs text-danger">{erreur}</p>}
    </div>
  );
}
