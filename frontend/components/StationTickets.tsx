"use client";

import { useRef, useState } from "react";

import { ApiError } from "@/lib/api";
import { joindreJustificatifChauffeur } from "@/lib/auth-chauffeur";
import { formatMontant } from "@/lib/format";
import {
  TICKETS_PAR_PAGE,
  categorieDe,
  categorieIncertaine,
  ticketPrioritaire,
} from "@/lib/tickets";
import type { TransactionVue } from "@/lib/types";

const JOUR = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long" });
const ANNEAU =
  "outline-none focus-visible:shadow-focus-detache";

export { ticketPrioritaire };

/** Le ticket se pose sur la dépense qui ne se classe pas sans lui. */
export function StationTickets({
  dossierId,
  depenses,
  onJointe,
}: {
  dossierId: string;
  depenses: TransactionVue[];
  onJointe: (transaction: TransactionVue) => void;
}) {
  const [ouvert, setOuvert] = useState(false);
  const [plafond, setPlafond] = useState(TICKETS_PAR_PAGE);
  const prioritaires = depenses
    .filter(ticketPrioritaire)
    .sort(
      (a, b) =>
        rang(a) - rang(b) ||
        b.date.localeCompare(a.date) ||
        b.ecriture_id.localeCompare(a.ecriture_id),
    );

  if (prioritaires.length === 0) return null;
  const visibles = ouvert ? prioritaires.slice(0, plafond) : [];

  return (
    <section className="mt-6 border-b border-hairline pb-4">
      <h2>
        <button
          type="button"
          aria-expanded={ouvert}
          onClick={() => setOuvert((valeur) => !valeur)}
          className={`flex min-h-11 w-full items-center text-left text-base font-semibold text-ink ${ANNEAU}`}
        >
          {ouvert ? "Replier les tickets" : `Tickets · ${prioritaires.length}`}
        </button>
      </h2>
      <p className="mt-1 text-sm text-subtle">{phrase(prioritaires.length)}</p>
      {visibles.length > 0 && (
        <ul className="mt-2">
          {visibles.map((depense) => (
            <LigneTicket
              key={depense.ecriture_id}
              dossierId={dossierId}
              depense={depense}
              onJointe={onJointe}
            />
          ))}
        </ul>
      )}
      {ouvert && prioritaires.length > plafond && (
        <button
          type="button"
          onClick={() => setPlafond((valeur) => valeur + TICKETS_PAR_PAGE)}
          className={`mt-2 min-h-11 rounded-md px-1 text-sm font-medium text-signal ${ANNEAU}`}
        >
          Voir la suite
        </button>
      )}
    </section>
  );
}

function phrase(nombre: number): string {
  if (nombre === 1) return "1 dépense ne se classe pas sans son ticket.";
  return `${nombre} dépenses ne se classent pas sans leur ticket.`;
}

function rang(depense: TransactionVue): number {
  const categorie = categorieDe(depense);
  if (categorie === null || categorieIncertaine(categorie)) return 0;
  return 1;
}

function LigneTicket({
  dossierId,
  depense,
  onJointe,
}: {
  dossierId: string;
  depense: TransactionVue;
  onJointe: (transaction: TransactionVue) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const nom = nomDepense(depense.libelle);
  const montant = formatMontant(depense.montant_cts);

  async function envoyer(fichier: File) {
    setEnvoi(true);
    setErreur(null);
    try {
      onJointe(await joindreJustificatifChauffeur(dossierId, depense.ecriture_id, fichier));
    } catch (exception) {
      setErreur(exception instanceof ApiError ? exception.message : "Échec de l'envoi de la photo.");
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <li className="border-b border-hairline py-3 last:border-b-0">
      <div className="flex items-baseline justify-between gap-4">
        <span className="min-w-0">
          <span className="block truncate text-base font-semibold text-ink">{nom}</span>
          <span className="mt-0.5 block text-sm text-subtle">{libelleJour(depense.date)}</span>
          <span className="mt-0.5 block text-sm text-subtle">{pourquoi(depense)}</span>
        </span>
        <span className="shrink-0 text-base font-semibold tabular-nums text-amount-negative">{montant}</span>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        aria-label={`Photo du ticket pour ${nom}, ${montant}`}
        onChange={(evenement) => {
          const fichier = evenement.target.files?.[0];
          if (fichier) void envoyer(fichier);
          evenement.target.value = "";
        }}
      />
      <button
        type="button"
        disabled={envoi}
        onClick={() => inputRef.current?.click()}
        className={`mt-1 inline-flex min-h-11 items-center rounded-md px-1 text-sm font-medium text-signal disabled:opacity-50 ${ANNEAU}`}
      >
        {envoi ? "Envoi…" : `Ajouter le ticket de ${nom}`}
      </button>
      {erreur && <p className="mt-1 text-xs text-danger">{erreur}</p>}
    </li>
  );
}

function nomDepense(libelle: string): string {
  const trouve = libelle.match(/^(.*)\s+\(([a-z0-9_]+)\)$/);
  return (trouve?.[1] ?? libelle).trim();
}

function pourquoi(depense: TransactionVue): string {
  const categorie = categorieDe(depense);
  if (categorie === "usage_personnel_suspect") {
    return "Le libellé ne dit pas ce qui a été acheté.";
  }
  if (categorie === "repas_et_receptions") {
    return "Repas de travail ou dépense personnelle : le ticket tranche.";
  }
  if (categorie === null || categorieIncertaine(categorie)) {
    return "Rien ne permet de la classer sans le ticket.";
  }
  return "Le libellé ne suffit pas à la classer.";
}

function libelleJour(jour: string): string {
  return JOUR.format(new Date(`${jour.slice(0, 10)}T12:00:00`));
}
