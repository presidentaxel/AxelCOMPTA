"use client";

import { useRef, useState } from "react";

import { QuestionCategorisation } from "@/components/QuestionCategorisation";
import { ApiError } from "@/lib/api";
import { joindreJustificatifChauffeur } from "@/lib/auth-chauffeur";
import { formatMontant } from "@/lib/format";
import { libelleCategorie } from "@/lib/libelles-chauffeur";
import type { TransactionVue } from "@/lib/types";

const JOUR = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long" });
const ANNEAU =
  "outline-none focus-visible:shadow-[0_0_0_2px_#fff,0_0_0_4px_#2563eb]";

/** Le libellé bancaire suffit : le ticket ne sert pas à classer. */
const CATEGORIES_CLAIRES = new Set([
  "carburant",
  "peage_stationnement",
  "entretien_reparation_vehicule",
  "assurance_vehicule",
  "telecommunications",
  "recettes_plateformes",
  "amendes_infractions",
  "honoraires_comptable_juridique",
  "charges_sociales_impots",
  "loyers_locations",
  "virement_interne",
  "compte_courant_associe",
  "remuneration_dirigeant",
  "frais_bancaires",
  "abonnements_logiciels",
  "fournitures_administratives",
  "subventions",
  "salaires_personnel",
  "usage_personnel",
]);

/** Le ticket est ce qui permet de savoir ce qui a été acheté. */
function categorieIncertaine(categorie: string): boolean {
  return (
    categorie === "usage_personnel_suspect" ||
    categorie === "non_categorise_a_verifier" ||
    categorie.startsWith("a_verifier")
  );
}

/** Priorité : la pièce sert à lire l'achat et à classer l'écriture.
 * Une dépense déjà claire (carburant, péage, téléphone…) n'est pas demandée. */
export function ticketPrioritaire(depense: TransactionVue): boolean {
  if (depense.montant_cts >= 0 || depense.a_justificatif) return false;
  const categorie = categorieDe(depense);
  if (categorie !== null && categorieIncertaine(categorie)) return true;
  if (depense.statut !== "à trancher") return false;
  return categorie === null || !CATEGORIES_CLAIRES.has(categorie);
}

/** Le ticket se pose sur la dépense qui ne se classe pas sans lui. */
export function StationTickets({
  dossierId,
  depenses,
  onJointe,
  onTranche,
}: {
  dossierId: string;
  depenses: TransactionVue[];
  onJointe: (transaction: TransactionVue) => void;
  onTranche: (transaction: TransactionVue, libelle: string) => void;
}) {
  const [ouvert, setOuvert] = useState(false);
  const [index, setIndex] = useState(0);
  const prioritaires = depenses
    .filter(ticketPrioritaire)
    .sort(
      (a, b) =>
        rang(a) - rang(b) ||
        b.date.localeCompare(a.date) ||
        b.ecriture_id.localeCompare(a.ecriture_id),
    );

  if (prioritaires.length === 0) return null;
  const place = Math.min(index, prioritaires.length - 1);
  const courant = prioritaires[place];
  if (!courant) return null;

  return (
    <section className="mt-6 border-b border-hairline pb-4">
      <button
        type="button"
        aria-expanded={ouvert}
        onClick={() => setOuvert((actuel) => !actuel)}
        className={`flex min-h-11 w-full items-center justify-between text-left ${ANNEAU}`}
      >
        <span>
          <span className="block text-base font-semibold text-ink">Tickets · {prioritaires.length}</span>
          <span className="mt-0.5 block text-sm text-subtle">{phrase(prioritaires.length)}</span>
        </span>
        <span className="text-sm font-medium text-primary">{ouvert ? "Replier" : "Voir"}</span>
      </button>
      {ouvert && (
        <div className="mt-3">
          <p className="text-sm font-medium text-ink">
            {place + 1} sur {prioritaires.length}
          </p>
          <LigneTicket dossierId={dossierId} depense={courant} onJointe={onJointe} />
          {courant.statut === "à trancher" && (
            <div className="mt-3">
              <QuestionCategorisation
                dossierId={dossierId}
                ecritureId={courant.ecriture_id}
                montantCts={courant.montant_cts}
                proposition={
                  courant.proposition
                    ? { code: courant.proposition, libelle: libelleCategorie(courant.proposition) }
                    : null
                }
                origine={courant.origine_proposition}
                onResolu={(transaction, libelle) => {
                  onTranche(transaction, libelle);
                  setIndex(place);
                }}
              />
            </div>
          )}
        </div>
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
        className={`mt-1 inline-flex min-h-11 items-center rounded-md px-1 text-sm font-medium text-primary disabled:opacity-50 ${ANNEAU}`}
      >
        {envoi ? "Envoi…" : `Ajouter le ticket de ${nom}`}
      </button>
      {erreur && (
        <p role="alert" className="mt-1 text-sm text-danger">
          {erreur}
        </p>
      )}
    </li>
  );
}

function nomDepense(libelle: string): string {
  const trouve = libelle.match(/^(.*)\s+\(([a-z0-9_]+)\)$/);
  return (trouve?.[1] ?? libelle).trim();
}

function categorieDe(depense: TransactionVue): string | null {
  const trouve = depense.libelle.match(/\(([a-z0-9_]+)\)$/);
  return trouve?.[1] ?? depense.proposition;
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
