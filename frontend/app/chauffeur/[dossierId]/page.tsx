"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { use, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ConfirmationGroupee } from "@/components/ConfirmationGroupee";
import { QuestionCategorisation } from "@/components/QuestionCategorisation";
import { StationTickets, ticketPrioritaire } from "@/components/StationTickets";
import { useDossierChauffeur } from "@/app/chauffeur/use-dossier";
import { ApiError } from "@/lib/api";
import { joindreJustificatifChauffeur } from "@/lib/auth-chauffeur";
import { formatMontant } from "@/lib/format";
import type { TransactionVue } from "@/lib/types";

const MOIS = new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric" });
const JOUR = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long" });
const ANNEAU =
  "outline-none focus-visible:shadow-[0_0_0_2px_#fff,0_0_0_4px_#2563eb]";

/** Activité : d'abord l'arriéré, qui se termine. Les mouvements déjà traités
 * se lisent mois par mois, comme un relevé, pas comme une file sans fin. */
export default function DossierChauffeurPage({
  params,
}: {
  params: Promise<{ dossierId: string }>;
}) {
  const { dossierId } = use(params);
  const { charge, remplacer, recharger } = useDossierChauffeur(dossierId);
  const [vue, setVue] = useState<"traiter" | "mouvements">("traiter");
  const [moisChoisi, setMoisChoisi] = useState<string | null>(null);

  if (charge.statut === "en_cours") {
    return <p className="text-sm text-subtle">Chargement…</p>;
  }
  if (charge.statut === "erreur") {
    return <p className="text-sm text-danger">{charge.message}</p>;
  }

  const { dossier, transactions } = charge;
  const aVerifier = transactions
    .filter((transaction) => transaction.statut === "à trancher")
    .sort((a, b) => b.date.localeCompare(a.date));
  const moisDispo = [
    ...new Set(transactions.map((transaction) => transaction.date.slice(0, 7))),
  ].sort();
  const dernierMois = moisDispo.at(-1);
  const mois = moisChoisi && moisDispo.includes(moisChoisi) ? moisChoisi : dernierMois;
  const indexMois = mois ? moisDispo.indexOf(mois) : -1;

  return (
    <div>
      <h1 className="text-[28px] font-bold tracking-tight text-ink">{dossier.nom}</h1>
      <p className="mt-1 text-sm text-subtle">
        {dossier.forme_juridique} · {dossier.regime_libelle}
      </p>
      <p
        className={`mt-6 text-[28px] font-bold tabular-nums tracking-tight ${
          dossier.resultat_cts < 0 ? "text-amount-negative" : "text-amount-positive"
        }`}
      >
        {formatMontant(dossier.resultat_cts)}
      </p>
      <p className="text-sm text-subtle">Résultat de l&apos;exercice</p>
      <ConnexionBancaire
        peutConnecter={dossier.peut_connecter_sa_banque}
        aDesTransactions={transactions.length > 0}
      />
      <div className="mt-8 flex gap-2">
        <Onglet actif={vue === "traiter"} onClick={() => setVue("traiter")}>
          {aVerifier.length > 0 ? `À traiter · ${aVerifier.length}` : "À traiter"}
        </Onglet>
        <Onglet actif={vue === "mouvements"} onClick={() => setVue("mouvements")}>
          Mouvements
        </Onglet>
      </div>
      {vue === "traiter" ? (
        <Arriere
          aVerifier={aVerifier}
          dossierId={dossierId}
          depenses={transactions.filter(ticketPrioritaire)}
          onChange={remplacer}
          onTranche={(transaction) => {
            remplacer(transaction);
            recharger();
          }}
          onGroupeTranche={recharger}
        />
      ) : (
        <Mouvements
          dossierId={dossierId}
          onJointe={remplacer}
          transactions={transactions.filter((transaction) => transaction.date.startsWith(mois ?? ""))}
          mois={mois}
          peutReculer={indexMois > 0}
          peutAvancer={indexMois >= 0 && indexMois < moisDispo.length - 1}
          onReculer={() => setMoisChoisi(moisDispo[indexMois - 1] ?? null)}
          onAvancer={() => setMoisChoisi(moisDispo[indexMois + 1] ?? null)}
        />
      )}
    </div>
  );
}

function Onglet({
  actif,
  onClick,
  children,
}: {
  actif: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={actif}
      onClick={onClick}
      className={`h-9 rounded-full px-4 text-sm font-medium ${ANNEAU} ${
        actif ? "bg-ink text-canvas" : "text-subtle"
      }`}
    >
      {children}
    </button>
  );
}

function Arriere({
  aVerifier,
  dossierId,
  depenses,
  onChange,
  onTranche,
  onGroupeTranche,
}: {
  aVerifier: TransactionVue[];
  dossierId: string;
  depenses: TransactionVue[];
  onChange: (transaction: TransactionVue) => void;
  onTranche: (transaction: TransactionVue) => void;
  onGroupeTranche: () => void;
}) {
  const premiereConfirmable = aVerifier.find(
    (transaction) =>
      transaction.proposition !== null &&
      confirmable(transaction.proposition, transaction.origine_proposition),
  )?.ecriture_id;
  if (aVerifier.length === 0 && depenses.length === 0) {
    return <p className="mt-10 text-sm text-subtle">Tout est à jour.</p>;
  }
  return (
    <div>
      <StationTickets dossierId={dossierId} depenses={depenses} onJointe={onChange} />
      {groupesSemblables(aVerifier).map(([categorie, operations]) => (
        <ConfirmationGroupee
          key={categorie}
          dossierId={dossierId}
          categorie={categorie}
          libelle={libelleCategorie(categorie)}
          operations={operations.map((operation) => ({
            ecritureId: operation.ecriture_id,
            nom: presenter(operation.libelle).nom,
            montantCts: operation.montant_cts,
          }))}
          onConfirme={onGroupeTranche}
        />
      ))}
      <ul className="mt-2">
        {aVerifier.map((transaction) => {
          const { nom } = presenter(transaction.libelle);
          const proposition = transaction.proposition
            ? { code: transaction.proposition, libelle: libelleCategorie(transaction.proposition) }
            : null;
          const confirmableIci =
            proposition !== null &&
            confirmable(proposition.code, transaction.origine_proposition);
          return (
            <li key={transaction.ecriture_id} className="min-w-0 border-b border-hairline py-4">
              <LigneMontant
                nom={nom}
                detail={proposition?.libelle ?? null}
                transaction={transaction}
              />
              <div className="mt-3">
                <QuestionCategorisation
                  dossierId={dossierId}
                  ecritureId={transaction.ecriture_id}
                  proposition={confirmableIci ? proposition : null}
                  origine={transaction.origine_proposition}
                  confiance={transaction.confiance_proposition}
                  sansProposition={proposition === null}
                  raccourci={confirmableIci && transaction.ecriture_id === premiereConfirmable}
                  onResolu={onTranche}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Opérations à trancher qui ressemblent à une opération déjà classée, par
 * catégorie. Un groupe d'une seule opération n'a pas besoin de raccourci. */
function groupesSemblables(aVerifier: TransactionVue[]): [string, TransactionVue[]][] {
  const groupes = new Map<string, TransactionVue[]>();
  for (const transaction of aVerifier) {
    if (transaction.origine_proposition !== "appris" || !transaction.proposition) continue;
    groupes.set(transaction.proposition, [
      ...(groupes.get(transaction.proposition) ?? []),
      transaction,
    ]);
  }
  return [...groupes.entries()].filter(([, operations]) => operations.length >= 2);
}

function Mouvements({
  dossierId,
  onJointe,
  transactions,
  mois,
  peutReculer,
  peutAvancer,
  onReculer,
  onAvancer,
}: {
  dossierId: string;
  onJointe: (transaction: TransactionVue) => void;
  transactions: TransactionVue[];
  mois: string | undefined;
  peutReculer: boolean;
  peutAvancer: boolean;
  onReculer: () => void;
  onAvancer: () => void;
}) {
  const [sens, setSens] = useState<"sorties" | "entrees">("sorties");
  const retenues = transactions.filter((transaction) =>
    sens === "sorties" ? transaction.montant_cts < 0 : transaction.montant_cts > 0,
  );
  const total = retenues.reduce((somme, transaction) => somme + transaction.montant_cts, 0);
  const jours = grouperParJour(retenues);
  return (
    <div className="mt-6">
      <div className="flex items-center justify-between">
        <button
          type="button"
          aria-label="Mois précédent"
          disabled={!peutReculer}
          onClick={onReculer}
          className={`flex h-11 w-11 items-center justify-center rounded-full text-ink disabled:text-faint ${ANNEAU}`}
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <p className="text-sm font-medium text-ink capitalize">{mois ? libelleMois(mois) : "Aucun mois"}</p>
        <button
          type="button"
          aria-label="Mois suivant"
          disabled={!peutAvancer}
          onClick={onAvancer}
          className={`flex h-11 w-11 items-center justify-center rounded-full text-ink disabled:text-faint ${ANNEAU}`}
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      </div>
      <div className="mt-2 flex gap-2">
        <Onglet actif={sens === "sorties"} onClick={() => setSens("sorties")}>
          Sorties
        </Onglet>
        <Onglet actif={sens === "entrees"} onClick={() => setSens("entrees")}>
          Entrées
        </Onglet>
      </div>
      {jours.length > 0 && (
        <p
          className={`mt-4 text-lg font-semibold tabular-nums ${
            total < 0 ? "text-amount-negative" : "text-amount-positive"
          }`}
        >
          {formatMontant(total)}
        </p>
      )}
      {jours.length === 0 ? (
        <p className="mt-6 text-sm text-subtle">
          {sens === "sorties" ? "Aucune sortie ce mois-ci." : "Aucune entrée ce mois-ci."}
        </p>
      ) : (
        jours.map(([jour, lignes]) => (
          <section key={jour} className="mt-6">
            <h2 className="text-sm font-medium text-subtle">{libelleJour(jour)}</h2>
            <ul>
              {lignes.map((transaction) => {
                const { nom, detail } = presenter(transaction.libelle);
                return (
                  <li key={transaction.ecriture_id} className="border-b border-hairline py-3">
                    <LigneMontant nom={nom} detail={detail} transaction={transaction} />
                    {sens === "sorties" && (
                      <AjouterTicketSortie
                        dossierId={dossierId}
                        transaction={transaction}
                        onJointe={onJointe}
                      />
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        ))
      )}
    </div>
  );
}

function AjouterTicketSortie({
  dossierId,
  transaction,
  onJointe,
}: {
  dossierId: string;
  transaction: TransactionVue;
  onJointe: (transaction: TransactionVue) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  if (transaction.a_justificatif) {
    return <p className="mt-1 text-sm text-validated">Ticket joint</p>;
  }

  async function envoyer(fichier: File) {
    setEnvoi(true);
    setErreur(null);
    try {
      onJointe(await joindreJustificatifChauffeur(dossierId, transaction.ecriture_id, fichier));
    } catch (exception) {
      setErreur(exception instanceof ApiError ? exception.message : "Échec de l'envoi de la photo.");
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
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
        className={`mt-1 rounded-md px-1 py-1 text-sm font-medium text-primary disabled:opacity-50 ${ANNEAU}`}
      >
        {envoi ? "Envoi…" : "Ajouter un ticket"}
      </button>
      {erreur && <p className="mt-1 text-xs text-danger">{erreur}</p>}
    </div>
  );
}

function LigneMontant({
  nom,
  detail,
  transaction,
}: {
  nom: string;
  detail: string | null;
  transaction: TransactionVue;
}) {
  const negatif = transaction.montant_cts < 0;
  return (
    <div className="flex items-baseline justify-between gap-4">
      <span className="min-w-0">
        <span className="block truncate text-base font-semibold text-ink">{nom}</span>
        {detail && <span className="mt-0.5 block text-sm text-subtle">{detail}</span>}
      </span>
      <span
        className={`shrink-0 text-base font-semibold tabular-nums ${
          negatif ? "text-amount-negative" : "text-amount-positive"
        }`}
      >
        {formatMontant(transaction.montant_cts)}
      </span>
    </div>
  );
}

function ConnexionBancaire({
  peutConnecter,
  aDesTransactions,
}: {
  peutConnecter: boolean;
  aDesTransactions: boolean;
}) {
  if (peutConnecter) {
    return (
      <Button type="button" variant="secondary" className="mt-6 w-full" disabled title="Bientôt disponible">
        Connecter ma banque
      </Button>
    );
  }
  if (!aDesTransactions) {
    return <p className="mt-6 text-sm text-subtle">Vos transactions arrivent bientôt.</p>;
  }
  return null;
}

const DETAILS: Record<string, string> = {
  usage_personnel_suspect: "À confirmer",
  usage_personnel: "Dépense personnelle",
  carburant: "Carburant",
  peage_stationnement: "Péage",
  repas_et_receptions: "Repas",
  assurance_vehicule: "Assurance",
  telecommunications: "Téléphone",
  entretien_reparation_vehicule: "Entretien",
  charges_sociales_impots: "Charges",
  honoraires_comptable_juridique: "Honoraires",
  recettes_plateformes: "Courses",
  remuneration_dirigeant: "Ma rémunération",
  compte_courant_associe: "Compte courant d'associé",
  virement_interne: "Virement entre mes comptes",
  salaires_personnel: "Salaire d'un salarié",
  frais_bancaires: "Frais bancaires",
  abonnements_logiciels: "Abonnement",
  fournitures_administratives: "Fournitures",
  amendes_infractions: "Amende",
  subventions: "Aide publique",
};

function libelleCategorie(code: string): string {
  return DETAILS[code] ?? code.replaceAll("_", " ");
}

/** Une proposition se confirme en un geste, sauf quand la réponse est déjà
 * l'un des boutons ou que la catégorie elle-même demande de vérifier. Une
 * proposition tirée des choix du chauffeur se confirme toujours. */
function confirmable(code: string, origine: TransactionVue["origine_proposition"]): boolean {
  if (origine === "appris") return true;
  return !(
    code === "non_categorise_a_verifier" ||
    code === "usage_personnel" ||
    code === "usage_personnel_suspect" ||
    code === "remuneration_dirigeant" ||
    code.startsWith("a_verifier")
  );
}

function presenter(libelle: string): { nom: string; detail: string | null } {
  const trouve = libelle.match(/^(.*)\s+\(([a-z0-9_]+)\)$/);
  if (!trouve?.[1] || !trouve[2]) return { nom: libelle, detail: null };
  return { nom: trouve[1], detail: libelleCategorie(trouve[2]) };
}

function grouperParJour(transactions: TransactionVue[]): [string, TransactionVue[]][] {
  const groupes = new Map<string, TransactionVue[]>();
  for (const transaction of [...transactions].sort((a, b) => b.date.localeCompare(a.date))) {
    const jour = transaction.date.slice(0, 10);
    groupes.set(jour, [...(groupes.get(jour) ?? []), transaction]);
  }
  return [...groupes.entries()];
}

function libelleMois(mois: string): string {
  return MOIS.format(new Date(`${mois}-01T12:00:00`));
}

function libelleJour(jour: string): string {
  return JOUR.format(new Date(`${jour}T12:00:00`));
}
