"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";

/** Entreprises retirées de la liste : les écritures sont gardées, un
 * administrateur peut les remettre. */
export function RetireesDeLaListe({
  retires,
  admin,
  onRemettre,
}: {
  retires: { dossier_id: string; nom: string }[];
  admin: boolean;
  /** Remet l'entreprise dans la liste ; la promesse échoue si le serveur refuse. */
  onRemettre: (dossierId: string) => Promise<void>;
}) {
  const [erreur, setErreur] = useState<string | null>(null);
  if (retires.length === 0) return null;
  return (
    <section className="mt-6 rounded-lg border border-border bg-canvas p-4">
      <h2 className="text-sm font-semibold text-ink">Retirées de la liste</h2>
      <p className="mt-1 text-sm text-subtle">Les écritures sont gardées.</p>
      <ul className="mt-3">
        {retires.map((dossier) => (
          <li key={dossier.dossier_id} className="flex items-center justify-between border-b border-hairline py-2">
            <span className="text-sm text-ink">{dossier.nom}</span>
            {admin && (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  setErreur(null);
                  onRemettre(dossier.dossier_id).catch(() =>
                    setErreur(`Impossible de remettre ${dossier.nom} dans la liste. Réessayez dans un instant.`),
                  );
                }}
              >
                Remettre
              </Button>
            )}
          </li>
        ))}
      </ul>
      {erreur && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {erreur}
        </p>
      )}
    </section>
  );
}
