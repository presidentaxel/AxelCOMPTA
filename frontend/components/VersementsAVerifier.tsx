"use client";

import { Card } from "@/components/ui/card";
import type { VersementPlateforme } from "@/lib/auth-chauffeur";
import { formatDate, formatMontant } from "@/lib/format";
import { motifEnClair } from "@/lib/plateformes";

/** AXE-891 : un relevé de plateforme qu'on n'a pas su rapprocher seul reste
 * dans « À traiter » tant qu'il est à vérifier. Le gestionnaire en voit le
 * nombre ; le chauffeur voit le motif, en clair. */
export function VersementsAVerifier({ versements }: { versements: VersementPlateforme[] }) {
  if (versements.length === 0) return null;
  return (
    <Card className="mt-4 p-4">
      <h2 className="text-base font-semibold text-ink">
        {versements.length > 1
          ? `${versements.length} versements de plateforme à vérifier`
          : "1 versement de plateforme à vérifier"}
      </h2>
      <p className="mt-1 text-sm text-subtle">
        On n&apos;a pas pu les relier seuls au virement reçu en banque. Votre gestionnaire
        est prévenu.
      </p>
      <ul className="mt-2">
        {versements.map((v) => (
          <li key={`${v.plateforme}-${v.du}`} className="border-b border-hairline py-2 text-sm last:border-0">
            <p className="text-ink">
              {v.plateforme.charAt(0).toUpperCase() + v.plateforme.slice(1)} · du {formatDate(v.du)} au {formatDate(v.au)} ·{" "}
              <span className="tabular-nums">{formatMontant(v.verse_cts)}</span>
            </p>
            <p className="text-subtle">{motifEnClair(v.motif)}</p>
          </li>
        ))}
      </ul>
    </Card>
  );
}
