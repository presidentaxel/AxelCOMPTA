"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, use, useEffect, useRef, useState } from "react";

import { useDossierChauffeur, useOperationsChauffeur } from "@/app/chauffeur/use-dossier";
import { ConfirmationGroupee } from "@/components/ConfirmationGroupee";
import { EtatErreur, EtatVide } from "@/components/EtatChargement";
import { QuestionCategorisation } from "@/components/QuestionCategorisation";
import { ResultatACeJour } from "@/components/ResultatACeJour";
import { Squelette, SqueletteLignes } from "@/components/Squelette";
import { StationTickets, ticketPrioritaire } from "@/components/StationTickets";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { annulerDecisionChauffeur, joindreJustificatifChauffeur } from "@/lib/auth-chauffeur";
import { formatMontant } from "@/lib/format";
import { libelleCategorie } from "@/lib/libelles-chauffeur";
import { messageVisible } from "@/lib/messages";
import type { DossierResume, TransactionVue } from "@/lib/types";

const MOIS = new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric" });
const JOUR = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long" });
const ANNEAU =
  "outline-none focus-visible:shadow-[0_0_0_2px_#fff,0_0_0_4px_#2563eb]";

/** Activité : une opération à la fois. L'onglet et le mois restent dans
 * l'adresse, pour revenir dessus après Exercice ou Compte. */
export default function DossierChauffeurPage({
  params,
}: {
  params: Promise<{ dossierId: string }>;
}) {
  return (
    <Suspense fallback={<SqueletteLignes nombre={4} className="mt-6 h-14 w-full" />}>
      <Activite params={params} />
    </Suspense>
  );
}

function Activite({ params }: { params: Promise<{ dossierId: string }> }) {
  const { dossierId } = use(params);
  const router = useRouter();
  const recherche = useSearchParams();
  const { dossier, reessayer: reessayerDossier } = useDossierChauffeur(dossierId);
  const {
    transactions,
    remplacer,
    recharger,
    reessayer: reessayerOperations,
  } = useOperationsChauffeur(dossierId);
  const vue = recherche.get("vue") === "mouvements" ? "mouvements" : "traiter";
  const moisUrl = recherche.get("mois");
  const [tactile, setTactile] = useState(true);
  const [annonce, setAnnonce] = useState("");
  const [annulation, setAnnulation] = useState<{ ids: string[]; libelle: string } | null>(null);
  const [annulationEnCours, setAnnulationEnCours] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(pointer: coarse)");
    const appliquer = () => setTactile(media.matches);
    media.addEventListener("change", appliquer);
    appliquer();
    return () => media.removeEventListener("change", appliquer);
  }, []);

  useEffect(() => {
    if (recherche.get("vue")) {
      sessionStorage.setItem(`activite:${dossierId}`, recherche.toString());
      return;
    }
    const stocke = sessionStorage.getItem(`activite:${dossierId}`);
    if (stocke) {
      router.replace(`/chauffeur/${dossierId}?${stocke}`, { scroll: false });
    }
  }, [dossierId, recherche, router]);

  function memoriser(suivantVue: "traiter" | "mouvements", mois: string | null) {
    const q = new URLSearchParams();
    q.set("vue", suivantVue);
    if (mois) q.set("mois", mois);
    const texte = q.toString();
    sessionStorage.setItem(`activite:${dossierId}`, texte);
    router.replace(`/chauffeur/${dossierId}?${texte}`, { scroll: false });
  }

  const operations = transactions.statut === "pret" ? transactions.valeur : [];
  const aVerifier = operations
    .filter((transaction) => transaction.statut === "à trancher")
    .sort((a, b) => b.date.localeCompare(a.date));
  const moisDispo = [...new Set(operations.map((transaction) => transaction.date.slice(0, 7)))].sort();
  const dernierMois = moisDispo.at(-1);
  const mois = moisUrl && moisDispo.includes(moisUrl) ? moisUrl : dernierMois;
  const indexMois = mois ? moisDispo.indexOf(mois) : -1;

  function apresDecision(transaction: TransactionVue, libelle: string) {
    remplacer(transaction);
    setAnnonce(`Classée : ${libelle}.`);
    setAnnulation({ ids: [transaction.ecriture_id], libelle });
    recharger();
  }

  async function annuler() {
    if (!annulation) return;
    setAnnulationEnCours(true);
    try {
      for (const id of annulation.ids) {
        await annulerDecisionChauffeur(dossierId, id);
      }
      setAnnonce("Décision annulée. L'opération est de nouveau à traiter.");
      setAnnulation(null);
      recharger();
    } catch (exception) {
      setAnnonce(messageVisible(exception, "Impossible d'annuler."));
    } finally {
      setAnnulationEnCours(false);
    }
  }

  return (
    <div>
      <p className="sr-only" aria-live="polite">
        {annonce}
      </p>
      <Entete dossier={dossier} onReessayer={reessayerDossier} />
      <div className="mt-8 flex gap-2">
        <Onglet actif={vue === "traiter"} onClick={() => memoriser("traiter", mois ?? null)}>
          {aVerifier.length > 0 ? `À traiter · ${aVerifier.length}` : "À traiter"}
        </Onglet>
        <Onglet actif={vue === "mouvements"} onClick={() => memoriser("mouvements", mois ?? null)}>
          Mouvements
        </Onglet>
      </div>
      {transactions.statut === "erreur" ? (
        <EtatErreur message={transactions.message} onReessayer={reessayerOperations} />
      ) : transactions.statut === "en_cours" ? (
        <SqueletteLignes nombre={4} className="mt-6 h-14 w-full" />
      ) : operations.length === 0 ? (
        <EtatVide
          titre="Vos opérations ne sont pas encore arrivées."
          action="Actualiser"
          onAction={reessayerOperations}
        />
      ) : vue === "traiter" ? (
        <Arriere
          aVerifier={aVerifier}
          dossierId={dossierId}
          depenses={operations.filter(ticketPrioritaire)}
          tactile={tactile}
          onChange={remplacer}
          onTranche={apresDecision}
          onGroupe={(ids, libelle) => {
            setAnnonce(`${ids.length} opérations classées.`);
            setAnnulation({ ids, libelle });
            recharger();
          }}
          onVoirMouvements={() => memoriser("mouvements", mois ?? null)}
        />
      ) : (
        <Mouvements
          dossierId={dossierId}
          onJointe={remplacer}
          onCorrigee={apresDecision}
          transactions={operations.filter((transaction) => transaction.date.startsWith(mois ?? ""))}
          mois={mois}
          peutReculer={indexMois > 0}
          peutAvancer={indexMois >= 0 && indexMois < moisDispo.length - 1}
          onReculer={() => memoriser("mouvements", moisDispo[indexMois - 1] ?? null)}
          onAvancer={() => memoriser("mouvements", moisDispo[indexMois + 1] ?? null)}
          onActualiser={reessayerOperations}
        />
      )}
      {annulation && (
        <div className="fixed bottom-[calc(4.5rem+env(safe-area-inset-bottom))] left-1/2 z-30 w-[min(100%-2rem,28rem)] -translate-x-1/2 rounded-md border border-border bg-canvas p-3 shadow-md">
          <p className="text-sm text-ink">Classée : {annulation.libelle}.</p>
          <button
            type="button"
            className={`mt-2 min-h-11 text-sm font-semibold text-primary ${ANNEAU}`}
            disabled={annulationEnCours}
            onClick={() => void annuler()}
          >
            {annulationEnCours ? "Annulation…" : "Annuler"}
          </button>
        </div>
      )}
    </div>
  );
}

function Entete({
  dossier,
  onReessayer,
}: {
  dossier:
    | { statut: "en_cours" }
    | { statut: "pret"; valeur: DossierResume }
    | { statut: "erreur"; message: string };
  onReessayer: () => void;
}) {
  if (dossier.statut === "erreur") {
    return <EtatErreur message={dossier.message} onReessayer={onReessayer} />;
  }
  if (dossier.statut === "en_cours") {
    return (
      <div>
        <Squelette className="h-8 w-48" />
        <Squelette className="mt-2 h-4 w-40" />
        <Squelette className="mt-6 h-8 w-32" />
        <Squelette className="mt-2 h-4 w-36" />
      </div>
    );
  }
  const fiche = dossier.valeur;
  return (
    <>
      <h1 className="text-[28px] font-bold tracking-tight text-ink">{fiche.nom}</h1>
      <p className="mt-1 text-sm text-subtle">
        {fiche.forme_juridique} · {fiche.regime_libelle}
      </p>
      <ResultatACeJour centimes={fiche.resultat_cts} />
      {fiche.peut_connecter_sa_banque && (
        <div className="mt-6">
          <Button type="button" variant="secondary" className="h-11 w-full" disabled>
            Connecter ma banque
          </Button>
          <p className="mt-2 text-sm text-subtle">Bientôt disponible.</p>
        </div>
      )}
    </>
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
      className={`h-11 rounded-full px-4 text-sm font-medium ${ANNEAU} ${
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
  tactile,
  onChange,
  onTranche,
  onGroupe,
  onVoirMouvements,
}: {
  aVerifier: TransactionVue[];
  dossierId: string;
  depenses: TransactionVue[];
  tactile: boolean;
  onChange: (transaction: TransactionVue) => void;
  onTranche: (transaction: TransactionVue, libelle: string) => void;
  onGroupe: (ids: string[], libelle: string) => void;
  onVoirMouvements: () => void;
}) {
  const [index, setIndex] = useState(0);
  const carteRef = useRef<HTMLDivElement>(null);
  const questions = aVerifier.filter((transaction) => !ticketPrioritaire(transaction));
  const place = questions.length === 0 ? 0 : Math.min(index, questions.length - 1);
  const courante = questions[place];

  useEffect(() => {
    carteRef.current?.focus();
  }, [courante?.ecriture_id]);

  return (
    <div>
      <StationTickets
        dossierId={dossierId}
        depenses={depenses}
        onJointe={onChange}
        onTranche={onTranche}
      />
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
          onConfirme={() =>
            onGroupe(
              operations.map((operation) => operation.ecriture_id),
              libelleCategorie(categorie),
            )
          }
        />
      ))}
      {courante ? (
        <>
          <p className="sticky top-14 z-10 -mx-4 mt-4 border-b border-hairline bg-canvas-app px-4 py-2 text-sm font-medium text-ink">
            {place + 1} sur {questions.length}
          </p>
          <div ref={carteRef} tabIndex={-1} className="min-w-0 py-4 outline-none">
            <LigneMontant
              nom={presenter(courante.libelle).nom}
              detail={
                courante.proposition ? libelleCategorie(courante.proposition) : null
              }
              transaction={courante}
            />
            <div className="mt-3">
              <QuestionCategorisation
                dossierId={dossierId}
                ecritureId={courante.ecriture_id}
                montantCts={courante.montant_cts}
                proposition={
                  courante.proposition &&
                  confirmable(courante.proposition, courante.origine_proposition)
                    ? {
                        code: courante.proposition,
                        libelle: libelleCategorie(courante.proposition),
                      }
                    : null
                }
                origine={courante.origine_proposition}
                raccourci={!tactile && courante.proposition !== null}
                onResolu={(transaction, libelle) => {
                  onTranche(transaction, libelle);
                  setIndex(place);
                }}
              />
            </div>
          </div>
        </>
      ) : (
        depenses.length === 0 && (
          <EtatVide
            titre="Tout est à jour."
            action="Voir mes mouvements"
            onAction={onVoirMouvements}
          />
        )
      )}
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
  onCorrigee,
  transactions,
  mois,
  peutReculer,
  peutAvancer,
  onReculer,
  onAvancer,
  onActualiser,
}: {
  dossierId: string;
  onJointe: (transaction: TransactionVue) => void;
  onCorrigee: (transaction: TransactionVue, libelle: string) => void;
  transactions: TransactionVue[];
  mois: string | undefined;
  peutReculer: boolean;
  peutAvancer: boolean;
  onReculer: () => void;
  onAvancer: () => void;
  onActualiser: () => void;
}) {
  const [sens, setSens] = useState<"sorties" | "entrees">("sorties");
  const [corrigeId, setCorrigeId] = useState<string | null>(null);
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
        <p className="text-sm font-medium text-ink capitalize">
          {mois ? libelleMois(mois) : "Aucun mois"}
        </p>
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
      {!mois ? (
        <EtatVide titre="Aucun mois à afficher." action="Actualiser" onAction={onActualiser} />
      ) : (
        <>
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
            <EtatVide
              titre={sens === "sorties" ? "Aucune sortie ce mois-ci." : "Aucune entrée ce mois-ci."}
              action={sens === "sorties" ? "Voir les entrées" : "Voir les sorties"}
              onAction={() => setSens(sens === "sorties" ? "entrees" : "sorties")}
            />
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
                        {corrigeId === transaction.ecriture_id ? (
                          <div className="mt-3">
                            <QuestionCategorisation
                              dossierId={dossierId}
                              ecritureId={transaction.ecriture_id}
                              montantCts={transaction.montant_cts}
                              proposition={null}
                              corriger
                              onResolu={(maj, libelle) => {
                                onCorrigee(maj, libelle);
                                setCorrigeId(null);
                              }}
                            />
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setCorrigeId(transaction.ecriture_id)}
                            className={`mt-1 min-h-11 rounded-md px-1 text-sm font-medium text-primary ${ANNEAU}`}
                          >
                            Corriger
                          </button>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))
          )}
        </>
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
        className={`mt-1 min-h-11 rounded-md px-1 text-sm font-medium text-primary disabled:opacity-50 ${ANNEAU}`}
      >
        {envoi ? "Envoi…" : "Ajouter un ticket"}
      </button>
      {erreur && (
        <p role="alert" className="mt-1 text-sm text-danger">
          {erreur}
        </p>
      )}
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
