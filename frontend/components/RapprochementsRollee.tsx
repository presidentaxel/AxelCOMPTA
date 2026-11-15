"use client";

import { useEffect, useMemo, useState } from "react";

import { Select } from "@/components/ui/select";
import { SelectRecherche } from "@/components/ui/select-recherche";
import { ErreurAuthGestionnaire, lireRapprochementsExpert } from "@/lib/auth-gestionnaire";
import { changer, type EtatClassees } from "@/lib/classees";
import { formatDate, formatMontant } from "@/lib/format";
import { messageEchecChargement } from "@/lib/session";
import type { SemaineRapprochement } from "@/lib/types";

const ETATS: Record<string, string> = {
  solde: "Soldée",
  en_attente: "En attente",
  a_verifier: "À vérifier",
};

const NATURES: Record<string, string> = {
  hebdomadaire: "Virement de la semaine",
  instantane: "Virement instantané",
};

/** Chaque semaine : ce que Rollee dit avoir gagné, et les virements reçus en banque. */
export function RapprochementsRollee({
  etat,
  chauffeurs,
  onChanger,
}: {
  etat: EtatClassees;
  chauffeurs: { id: string; nom: string }[];
  onChanger: (suivant: EtatClassees) => void;
}) {
  const [charge, setCharge] = useState<{ dossier: string; semaines: SemaineRapprochement[] } | null>(
    null,
  );
  const [erreur, setErreur] = useState<string | null>(null);
  const [filtre, setFiltre] = useState("toutes");
  const dossier = etat.chauffeur;
  const semaines = charge?.dossier === dossier ? charge.semaines : null;

  useEffect(() => {
    if (!dossier) return;
    let actif = true;
    lireRapprochementsExpert(dossier)
      .then((lues) => {
        if (actif) {
          setCharge({ dossier, semaines: lues });
          setErreur(null);
        }
      })
      .catch((exception: unknown) => {
        if (!actif) return;
        if (exception instanceof ErreurAuthGestionnaire) {
          setErreur("Session expirée.");
          return;
        }
        setErreur(messageEchecChargement(exception, "Les rapprochements n'ont pas pu être lus."));
      });
    return () => {
      actif = false;
    };
  }, [dossier]);

  const affichees = useMemo(
    () => (filtre === "toutes" ? (semaines ?? []) : (semaines ?? []).filter((s) => s.etat === filtre)),
    [filtre, semaines],
  );

  return (
    <div className="mt-6">
      <div className="flex flex-wrap items-center gap-2 text-sm text-subtle">
        Entreprise
        <SelectRecherche
          aria-label="Entreprise"
          value={dossier || "aucune"}
          onValueChange={(valeur) => onChanger(changer(etat, "chauffeur", valeur === "aucune" ? "" : valeur))}
          options={[
            { value: "aucune", label: "Choisir" },
            ...chauffeurs.map((chauffeur) => ({ value: chauffeur.id, label: chauffeur.nom })),
          ]}
          className="w-64"
        />
        <Select
          aria-label="État du rapprochement"
          value={filtre}
          onValueChange={setFiltre}
          options={[
            { value: "toutes", label: "Toutes les semaines" },
            ...Object.entries(ETATS).map(([id, libelle]) => ({ value: id, label: libelle })),
          ]}
          className="w-52"
        />
      </div>
      <p className="mt-3 text-sm text-subtle">
        Dû = gagné net moins les courses en espèces. Payé = virements de la plateforme reçus en
        banque. Les frais sont ceux des retraits instantanés.
      </p>
      {!dossier && <p className="mt-6 text-sm text-subtle">Choisissez une entreprise.</p>}
      {erreur && <p className="mt-6 text-sm text-danger">{erreur}</p>}
      {dossier && !erreur && semaines === null && (
        <p className="mt-6 text-sm text-subtle" aria-busy="true">
          Chargement des rapprochements…
        </p>
      )}
      {semaines && affichees.length === 0 && (
        <p className="mt-6 text-sm text-subtle">Aucune semaine pour ce filtre.</p>
      )}
      {affichees.length > 0 && (
        <div className="mt-4 divide-y divide-slate-100 border-t border-slate-100">
          {affichees.map((semaine) => (
            <Semaine key={`${semaine.plateforme}-${semaine.du}`} semaine={semaine} />
          ))}
        </div>
      )}
    </div>
  );
}

function Semaine({ semaine }: { semaine: SemaineRapprochement }) {
  return (
    <details className="py-3">
      <summary className="cursor-pointer text-sm text-ink">
        <span className="font-medium">{libellePlateforme(semaine.plateforme)}</span>
        <span className="text-subtle">
          {" "}
          · {formatDate(semaine.du)} – {formatDate(semaine.au)} · {ETATS[semaine.etat] ?? semaine.etat}
        </span>
        <span className="mt-1 grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-4">
          <Montant libelle="Dû" centimes={semaine.du_cts} />
          <Montant libelle="Payé" centimes={semaine.paye_cts} />
          <Montant libelle="Frais" centimes={semaine.frais_cts} />
          <Montant libelle="Écart" centimes={semaine.ecart_cts} />
        </span>
      </summary>
      {semaine.motif && <p className="mt-2 text-sm text-subtle">{semaine.motif}</p>}
      <Jours jours={semaine.jours} />
      <Virements virements={semaine.virements} />
    </details>
  );
}

function Montant({ libelle, centimes }: { libelle: string; centimes: number }) {
  return (
    <span className="text-sm">
      <span className="text-subtle">{libelle} </span>
      <span className="tabular-nums text-ink">{formatMontant(centimes)}</span>
    </span>
  );
}

function Jours({ jours }: { jours: SemaineRapprochement["jours"] }) {
  if (jours.length === 0) return <p className="mt-3 text-sm text-subtle">Aucun jour Rollee.</p>;
  return (
    <table className="mt-3 w-full text-sm">
      <caption className="mb-1 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
        Rollee
      </caption>
      <thead>
        <tr className="text-xs text-slate-500">
          <th className="px-2 py-1 text-left font-medium">Jour</th>
          <th className="px-2 py-1 text-right font-medium">Brut</th>
          <th className="px-2 py-1 text-right font-medium">Commission</th>
          <th className="px-2 py-1 text-right font-medium">Espèces</th>
          <th className="px-2 py-1 text-right font-medium">Net</th>
          <th className="px-2 py-1 text-right font-medium">Dû</th>
        </tr>
      </thead>
      <tbody>
        {jours.map((jour) => (
          <tr key={jour.date} className="border-t border-slate-100">
            <td className="px-2 py-1">{formatDate(jour.date)}</td>
            <td className="px-2 py-1 text-right tabular-nums">{formatMontant(jour.brut_cts)}</td>
            <td className="px-2 py-1 text-right tabular-nums">{formatMontant(jour.commission_cts)}</td>
            <td className="px-2 py-1 text-right tabular-nums">{formatMontant(jour.especes_cts)}</td>
            <td className="px-2 py-1 text-right tabular-nums">{formatMontant(jour.net_cts)}</td>
            <td className="px-2 py-1 text-right tabular-nums">{formatMontant(jour.du_cts)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Virements({ virements }: { virements: SemaineRapprochement["virements"] }) {
  if (virements.length === 0) return <p className="mt-3 text-sm text-subtle">Aucun virement en banque.</p>;
  return (
    <table className="mt-3 w-full text-sm">
      <caption className="mb-1 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
        Banque
      </caption>
      <thead>
        <tr className="text-xs text-slate-500">
          <th className="px-2 py-1 text-left font-medium">Date</th>
          <th className="px-2 py-1 text-left font-medium">Libellé</th>
          <th className="px-2 py-1 text-left font-medium">Nature</th>
          <th className="px-2 py-1 text-left font-medium">Compte</th>
          <th className="px-2 py-1 text-right font-medium">Montant</th>
        </tr>
      </thead>
      <tbody>
        {virements.map((virement) => (
          <tr key={`${virement.date}-${virement.libelle}-${virement.montant_cts}`} className="border-t border-slate-100">
            <td className="px-2 py-1">{formatDate(virement.date)}</td>
            <td className="px-2 py-1">{virement.libelle}</td>
            <td className="px-2 py-1">{NATURES[virement.nature] ?? virement.nature}</td>
            <td className="px-2 py-1 tabular-nums">{virement.compte}</td>
            <td className="px-2 py-1 text-right tabular-nums">{formatMontant(virement.montant_cts)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function libellePlateforme(nom: string): string {
  return nom ? nom.charAt(0).toUpperCase() + nom.slice(1) : nom;
}
