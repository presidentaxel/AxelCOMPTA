"use client";

import { useEffect, useState } from "react";

import { lireVersementsPlateformesChauffeur, type VersementPlateforme } from "@/lib/auth-chauffeur";
import { formatDate, formatMontant } from "@/lib/format";
import { etatVersement } from "@/lib/plateformes";

/** AXE-821 : chaque semaine (ou mois) de revenus lue chez Rollee — brut,
 * commission, versé — et son rapprochement avec le virement en banque. Le
 * chiffre d'affaires et la TVA viennent de là. Réservé au chauffeur. */
export function VersementsPlateformes({ dossierId }: { dossierId: string }) {
  const [versements, setVersements] = useState<VersementPlateforme[] | null>(null);
  useEffect(() => {
    let actif = true;
    lireVersementsPlateformesChauffeur(dossierId)
      .then((lus) => {
        if (actif) setVersements(lus);
      })
      .catch(() => {
        if (actif) setVersements([]);
      });
    return () => {
      actif = false;
    };
  }, [dossierId]);

  if (!versements || versements.length === 0) return null;
  return (
    <table className="mt-4 w-full text-sm">
      <caption className="mb-2 text-left text-sm font-medium text-ink">Derniers versements</caption>
      <thead>
        <tr className="h-9 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
          <th className="px-2 text-left">Période</th>
          <th className="px-2 text-right">Brut</th>
          <th className="px-2 text-right">Commission</th>
          <th className="px-2 text-right">Versé</th>
        </tr>
      </thead>
      <tbody>
        {versements.map((v) => (
          <tr key={`${v.plateforme}-${v.du}`} className="border-b border-slate-100 align-top">
            <td className="px-2 py-2 text-ink">
              {v.plateforme} · {formatDate(v.du)} au {formatDate(v.au)}
              <span className="block text-xs text-subtle">{etatVersement(v.etat, v.motif)}</span>
            </td>
            <td className="px-2 py-2 text-right tabular-nums">{formatMontant(v.brut_cts)}</td>
            <td className="px-2 py-2 text-right tabular-nums">{formatMontant(v.commission_cts)}</td>
            <td className="px-2 py-2 text-right tabular-nums">{formatMontant(v.verse_cts)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
