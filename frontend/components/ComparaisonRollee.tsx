"use client";

import { Fragment, useEffect, useState } from "react";

import {
  lireComparaisonRolleeChauffeur,
  type ComparaisonRollee as Comparaison,
  type TotauxCompares,
} from "@/lib/auth-chauffeur";
import { formatDate, formatMontant } from "@/lib/format";
import { comparaisonARegarder, etatComparaison } from "@/lib/plateformes";

const MOIS = new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric" });

/** AXE-928 : ce que Rollee dit gagné et ce que la banque a reçu, mois par
 * mois. La banque fait foi pour la compta ; Rollee montre ce qui manque
 * (compte bancaire pas ajouté, plateforme pas reliée). Une année sans banque
 * sert de rapport : CA des courses, TVA, revenus hors course, espèces. */
export function ComparaisonRollee({ dossierId }: { dossierId: string }) {
  const [annee, setAnnee] = useState<number | null>(null);
  const [donnees, setDonnees] = useState<Comparaison | null>(null);
  const [ouvert, setOuvert] = useState<string | null>(null);

  useEffect(() => {
    let actif = true;
    lireComparaisonRolleeChauffeur(dossierId, annee)
      .then((lues) => {
        if (actif) setDonnees(lues);
      })
      .catch(() => {
        if (actif) setDonnees(null);
      });
    return () => {
      actif = false;
    };
  }, [dossierId, annee]);

  if (!donnees || donnees.annees.length === 0) return null;
  const t = donnees.totaux;
  return (
    <div className="mt-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium text-ink">Rollee et la banque</h3>
        <label className="text-sm text-subtle">
          Année{" "}
          <select
            className="rounded border border-slate-200 px-2 py-1 text-ink"
            value={donnees.annee ?? ""}
            onChange={(e) => setAnnee(Number(e.target.value))}
          >
            {donnees.annees.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="mt-1 text-xs text-subtle">
        La banque fait foi pour la comptabilité. Rollee sert à voir s&apos;il manque un virement.
        {donnees.debut_banque
          ? ` Relevés bancaires depuis le ${formatDate(donnees.debut_banque)}.`
          : " Aucun relevé bancaire."}
      </p>
      <Rapport totaux={t} />
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[32rem] text-sm">
          <thead>
            <tr className="h-9 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <th className="px-2 text-left">Mois</th>
              <th className="px-2 text-right">Dû selon Rollee</th>
              <th className="px-2 text-right">Reçu en banque</th>
              <th className="px-2 text-right">Frais</th>
              <th className="px-2 text-right">Écart</th>
            </tr>
          </thead>
          <tbody>
            {donnees.mois.map((m) => {
              const aRegarder = m.semaines.filter((s) => comparaisonARegarder(s.etat)).length;
              const deplie = ouvert === m.mois;
              return (
                <Fragment key={m.mois}>
                  <tr className="border-b border-slate-100 align-top">
                    <td className="px-2 py-2 text-ink">
                      <button
                        type="button"
                        className="text-left underline-offset-2 hover:underline"
                        aria-expanded={deplie}
                        onClick={() => setOuvert(deplie ? null : m.mois)}
                      >
                        {MOIS.format(new Date(`${m.mois}T00:00:00`))}
                      </button>
                      {aRegarder > 0 && (
                        <span className="block text-xs text-danger">{aRegarder} semaine(s) à regarder</span>
                      )}
                    </td>
                    <Montants totaux={m.totaux} />
                  </tr>
                  {deplie &&
                    m.semaines.map((s) => (
                      <tr key={`${s.plateforme}-${s.lundi}`} className="border-b border-slate-50 bg-slate-50/50 text-xs">
                        <td className="py-1.5 pl-6 pr-2 text-ink">
                          {s.plateforme} · semaine du {formatDate(s.lundi)}
                          <span
                            className={`block ${comparaisonARegarder(s.etat) ? "text-danger" : "text-subtle"}`}
                          >
                            {etatComparaison(s.etat)}
                            {s.instantanes > 0 ? ` · ${s.instantanes} retrait(s) instantané(s)` : ""}
                          </span>
                        </td>
                        <Montants totaux={s.totaux} />
                      </tr>
                    ))}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Montants({ totaux }: { totaux: TotauxCompares }) {
  return (
    <>
      <td className="px-2 py-2 text-right tabular-nums">{formatMontant(totaux.du_cts)}</td>
      <td className="px-2 py-2 text-right tabular-nums">{formatMontant(totaux.verse_cts)}</td>
      <td className="px-2 py-2 text-right tabular-nums">{formatMontant(totaux.frais_cts)}</td>
      <td className="px-2 py-2 text-right tabular-nums">{formatMontant(totaux.ecart_cts)}</td>
    </>
  );
}

function Rapport({ totaux }: { totaux: TotauxCompares }) {
  const lignes: [string, number][] = [
    ["Gagné (après commission)", totaux.gagne_cts],
    ["Commission des plateformes", totaux.commission_cts],
    ["Courses hors taxe", totaux.courses_ht_cts],
    ["TVA sur les courses", totaux.tva_cts],
    ["Pourboires, bonus et autres (sans TVA)", totaux.hors_course_cts],
    ["Payé en espèces", totaux.especes_cts],
  ];
  return (
    <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
      {lignes.map(([libelle, montant]) => (
        <div key={libelle} className="flex justify-between gap-2 border-b border-slate-100 py-1">
          <dt className="text-subtle">{libelle}</dt>
          <dd className="tabular-nums text-ink">{formatMontant(montant)}</dd>
        </div>
      ))}
    </dl>
  );
}
