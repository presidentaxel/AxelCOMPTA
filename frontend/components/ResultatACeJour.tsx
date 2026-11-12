"use client";

import { formatDate, formatMontant } from "@/lib/format";
import type { DossierResume } from "@/lib/types";

/** Résultat provisoire du dossier, affiché tel quel sur Activité, Exercice
 * et Mon résultat. Source unique : le résumé du dossier. L'écran d'affectation
 * chiffre le résultat de l'exercice clos, qui peut diverger, et ne le
 * réaffiche pas sous un autre libellé. */
export function ResultatACeJour({ dossier }: { dossier: DossierResume }) {
  const centimes = dossier.resultat_cts;
  return (
    <div className="rounded-lg border border-border bg-canvas p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted" suppressHydrationWarning>
        Résultat à ce jour, {formatDate(aujourdhuiIso())}
      </p>
      <p
        className={`mt-1.5 text-4xl font-bold leading-tight tabular-nums tracking-tight ${
          centimes < 0 ? "text-amount-negative" : "text-amount-positive"
        }`}
      >
        {formatMontant(centimes)}
      </p>
    </div>
  );
}

function aujourdhuiIso(): string {
  const date = new Date();
  const mois = String(date.getMonth() + 1).padStart(2, "0");
  const jour = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${mois}-${jour}`;
}
