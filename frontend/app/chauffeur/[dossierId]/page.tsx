"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, use, useEffect, useRef, useState } from "react";

import {
  annonceAnnulee,
  annonceClassee,
  compteurFile,
  questionsRestantes,
  ticketsSeuls,
} from "@/app/chauffeur/file-a-traiter";
import {
  useDecisionDifferee,
  type DecisionEnAttente,
} from "@/app/chauffeur/use-decision-differee";
import { useDossierChauffeur, useOperationsChauffeur } from "@/app/chauffeur/use-dossier";
import { ConfirmationEntreprise } from "@/components/ConfirmationEntreprise";
import { EcartsRegistre } from "@/components/EcartsRegistre";
import { ConfirmationGroupee } from "@/components/ConfirmationGroupee";
import { Etat } from "@/components/Etat";
import { QuestionCategorisation } from "@/components/QuestionCategorisation";
import { QuestionRetrait } from "@/components/QuestionRetrait";
import { ResultatACeJour } from "@/components/ResultatACeJour";
import { Squelette, SqueletteLignes } from "@/components/Squelette";
import { StationTickets } from "@/components/StationTickets";
import { ToastDecision } from "@/components/ToastDecision";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  ecrireEtatActivite,
  lireEtatActivite,
  memoriserActivite,
  relireActivite,
  type EtatActivite,
  type SensActivite,
} from "@/lib/activite-url";
import {
  annulerDecisionChauffeur,
  corrigerTransactionChauffeur,
  joindreJustificatifChauffeur,
} from "@/lib/auth-chauffeur";
import { formatDate, formatMontant } from "@/lib/format";
import { libelleCategorie, phrasePourChauffeur } from "@/lib/langage-chauffeur";
import { estRetrait } from "@/lib/retrait-especes";
import { ticketPrioritaire } from "@/lib/tickets";
import { phraseTva } from "@/lib/tva-estimee";
import type { DossierResume, TransactionVue } from "@/lib/types";

const MOIS = new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric" });
const JOUR = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long" });
const ANNEAU =
  "outline-none focus-visible:shadow-focus-detache";

/** Activité : d'abord l'arriéré, qui se termine. Les mouvements déjà traités
 * se lisent mois par mois, comme un relevé, pas comme une file sans fin. */
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

function Activite({
  params,
}: {
  params: Promise<{ dossierId: string }>;
}) {
  const { dossierId } = use(params);
  const router = useRouter();
  const pathname = usePathname();
  const recherche = useSearchParams();
  const etat = lireEtatActivite(recherche);
  const requete = recherche.toString();
  const { dossier, reessayer: reessayerDossier } = useDossierChauffeur(dossierId);
  const {
    transactions,
    remplacer,
    recharger,
    reessayer: reessayerOperations,
  } = useOperationsChauffeur(dossierId);
  const [horsFile, setHorsFile] = useState<string[]>([]);
  const [epinglee, setEpinglee] = useState<string | null>(null);
  const [annonce, setAnnonce] = useState("");
  const [suit, setSuit] = useState(false);
  const [erreurAction, setErreurAction] = useState<string | null>(null);
  const [correction, setCorrection] = useState<CorrectionAffichee | null>(null);
  const [enCoursCorrection, setEnCoursCorrection] = useState(false);
  const [ouverte, setOuverte] = useState<string | null>(null);
  const [annulation, setAnnulation] = useState<{ ids: string[]; libelle: string } | null>(null);

  function enregistree(transaction: TransactionVue, decision: DecisionEnAttente) {
    remplacer(transaction);
    recharger();
    setAnnulation({ ids: [transaction.ecriture_id], libelle: decision.libelle });
  }

  function echec(original: TransactionVue, message: string) {
    setHorsFile((ids) => ids.filter((id) => id !== original.ecriture_id));
    remplacer(original);
    setEpinglee(original.ecriture_id);
    setErreurAction(phrasePourChauffeur(message));
    setAnnonce("L'enregistrement a échoué.");
    setSuit(true);
  }

  const { enAttente, poser, annuler } = useDecisionDifferee(dossierId, enregistree, echec);

  useEffect(() => {
    if (requete) {
      memoriserActivite(dossierId, requete);
      return;
    }
    const sauve = relireActivite(dossierId);
    if (!sauve) return;
    router.replace(`${pathname}?${sauve}`, { scroll: false });
  }, [dossierId, requete, pathname, router]);

  function mettreAJour(maj: Partial<EtatActivite>) {
    const suivante = ecrireEtatActivite(recherche, maj);
    memoriserActivite(dossierId, suivante);
    router.replace(suivante ? `${pathname}?${suivante}` : pathname, { scroll: false });
  }

  const operations = transactions.statut === "pret" ? transactions.valeur : [];
  const aVerifier = operations
    .filter((transaction) => transaction.statut === "à trancher")
    .sort((a, b) => b.date.localeCompare(a.date));
  const file = questionsRestantes(aVerifier, horsFile);
  const tickets = ticketsSeuls(operations);
  const { position, total } = compteurFile(file.length, horsFile.length, tickets.length);
  const courante =
    (epinglee ? file.find((operation) => operation.ecriture_id === epinglee) : undefined) ??
    file[0] ??
    null;
  const moisDispo = [...new Set(operations.map((transaction) => transaction.date.slice(0, 7)))].sort();
  const dernierMois = moisDispo.at(-1);
  const mois = etat.mois && moisDispo.includes(etat.mois) ? etat.mois : dernierMois;
  const indexMois = mois ? moisDispo.indexOf(mois) : -1;
  const reste = file.length + tickets.length;
  const sansOperation = transactions.statut === "pret" && operations.length === 0;
  const peutConnecter = dossier.statut === "pret" && dossier.valeur.peut_connecter_sa_banque;

  function reessayerEchecs() {
    if (dossier.statut === "erreur") reessayerDossier();
    if (transactions.statut === "erreur") reessayerOperations();
  }
  const toast = enAttente
    ? { libelle: enAttente.libelle, onAnnuler: annulerDecision }
    : correction
      ? { libelle: correction.libelle, onAnnuler: annulerDecision }
      : annulation
        ? { libelle: annulation.libelle, onAnnuler: () => void annulerSurLeServeur() }
        : null;

  function classer(transaction: TransactionVue, categorie: string, libelle: string) {
    setErreurAction(null);
    setCorrection(null);
    setAnnulation(null);
    if (transaction.statut === "validé") {
      void lancerCorrection(transaction, categorie, libelle);
      return;
    }
    const apres = file.filter((operation) => operation.ecriture_id !== transaction.ecriture_id);
    poser({ original: transaction, categorie, libelle });
    setHorsFile((ids) => (ids.includes(transaction.ecriture_id) ? ids : [...ids, transaction.ecriture_id]));
    setEpinglee(null);
    setOuverte(null);
    remplacer({ ...transaction, statut: "validé", categorie });
    setAnnonce(annonceClassee(presenter(transaction.libelle).nom, libelle, suiteApres(apres)));
    setSuit(true);
  }

  function suiteApres(apres: TransactionVue[]): string {
    const suivante = apres[0];
    if (suivante) return `Suivante : « ${presenter(suivante.libelle).nom} ».`;
    if (tickets.length > 0) return "Il reste des tickets.";
    return "Plus rien à traiter.";
  }

  async function lancerCorrection(transaction: TransactionVue, categorie: string, libelle: string) {
    const precedente = transaction.categorie ?? null;
    setEnCoursCorrection(true);
    try {
      remplacer(
        await corrigerTransactionChauffeur(dossierId, transaction.ecriture_id, categorie),
      );
      recharger();
      setOuverte(null);
      setAnnonce(annonceClassee(presenter(transaction.libelle).nom, libelle, null));
      if (precedente && precedente !== categorie) {
        setCorrection({ libelle, precedente, ecritureId: transaction.ecriture_id });
      }
    } catch (exception) {
      const message = exception instanceof ApiError ? exception.message : "Échec de l'envoi.";
      setErreurAction(phrasePourChauffeur(message));
      setAnnonce("L'enregistrement a échoué.");
    } finally {
      setEnCoursCorrection(false);
    }
  }

  function annulerDecision() {
    if (correction && !enAttente) {
      void annulerCorrection();
      return;
    }
    const decision = annuler();
    if (!decision) return;
    setHorsFile((ids) => ids.filter((id) => id !== decision.original.ecriture_id));
    remplacer(decision.original);
    setEpinglee(decision.original.ecriture_id);
    setAnnonce(annonceAnnulee(presenter(decision.original.libelle).nom));
    setSuit(true);
    setErreurAction(null);
  }

  async function annulerCorrection() {
    if (!correction) return;
    const { precedente, ecritureId } = correction;
    const operation = operations.find((ligne) => ligne.ecriture_id === ecritureId);
    setCorrection(null);
    setEnCoursCorrection(true);
    try {
      remplacer(await corrigerTransactionChauffeur(dossierId, ecritureId, precedente));
      setAnnonce(annonceAnnulee(operation ? presenter(operation.libelle).nom : "L'opération"));
    } catch (exception) {
      const message = exception instanceof ApiError ? exception.message : "Échec de l'envoi.";
      setErreurAction(phrasePourChauffeur(message));
    } finally {
      setEnCoursCorrection(false);
    }
  }

  async function annulerSurLeServeur() {
    if (!annulation) return;
    const enCours = annulation;
    setAnnulation(null);
    try {
      for (const id of enCours.ids) {
        await annulerDecisionChauffeur(dossierId, id);
      }
      setHorsFile((ids) => ids.filter((id) => !enCours.ids.includes(id)));
      setAnnonce("Décision annulée. L'opération est de nouveau à traiter.");
      recharger();
    } catch (exception) {
      setAnnulation(enCours);
      const message = exception instanceof ApiError ? exception.message : "Impossible d'annuler.";
      setErreurAction(phrasePourChauffeur(message));
    }
  }

  function confirmerGroupe(ids: string[], libelle: string) {
    setHorsFile((liste) => {
      const connus = new Set(liste);
      return [...liste, ...ids.filter((id) => !connus.has(id))];
    });
    setEpinglee(null);
    setAnnonce(
      ids.length > 1
        ? `${ids.length} opérations classées en « ${libelle} ».`
        : `1 opération classée en « ${libelle} ».`,
    );
    setSuit(true);
    setAnnulation({ ids, libelle });
    recharger();
  }

  return (
    <div>
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {annonce}
      </div>
      <Entete
        dossier={dossier}
        reste={transactions.statut === "pret" ? reste : null}
        onReessayer={reessayerEchecs}
      />
      <ConfirmationEntreprise dossierId={dossierId} />
      <EcartsRegistre dossierId={dossierId} />
      {transactions.statut === "pret" && !sansOperation && (
      <div className="sticky top-0 z-20 -mx-4 mt-8 bg-canvas-app px-4 pb-3 pt-1">
        <div className="flex gap-2">
          <Onglet actif={etat.vue === "traiter"} onClick={() => mettreAJour({ vue: "traiter" })}>
            {reste > 0 ? `À traiter · ${reste}` : "À traiter"}
          </Onglet>
          <Onglet actif={etat.vue === "mouvements"} onClick={() => mettreAJour({ vue: "mouvements" })}>
            Mouvements
          </Onglet>
        </div>
        {etat.vue === "traiter" && (file.length > 0 || tickets.length > 0) && (
          <p className="mt-3 text-sm font-medium text-ink">
            {file.length > 0
              ? `${position} sur ${total}`
              : tickets.length > 1
                ? `${tickets.length} tickets`
                : "1 ticket"}
          </p>
        )}
      </div>
      )}
      {erreurAction && (
        <p role="alert" className="mt-4 text-sm text-danger">
          {erreurAction}
        </p>
      )}
      {dossier.statut === "erreur" ? null : transactions.statut === "erreur" ? (
        <Etat type="erreur" message={transactions.message} onReessayer={reessayerOperations} />
      ) : transactions.statut === "en_cours" ? (
        <Etat type="chargement">
          <SqueletteLignes nombre={4} className="h-14 w-full" />
        </Etat>
      ) : sansOperation ? (
        peutConnecter ? null : (
          <Etat
            type="vide"
            message="Vos transactions arrivent bientôt."
            action={{ libelle: "Actualiser", onClick: reessayerOperations }}
          />
        )
      ) : etat.vue === "traiter" ? (
        <Arriere
          courante={courante}
          file={file}
          tickets={tickets}
          dossierId={dossierId}
          suit={suit}
          erreur={erreurAction}
          onChange={remplacer}
          onChoisir={classer}
          onGroupe={confirmerGroupe}
          onVoirMouvements={() => mettreAJour({ vue: "mouvements" })}
        />
      ) : (
        <Mouvements
          dossierId={dossierId}
          ouverte={ouverte}
          enCours={enCoursCorrection}
          erreur={erreurAction}
          onOuvrir={setOuverte}
          onChoisir={classer}
          onJointe={remplacer}
          transactions={operations.filter((transaction) => transaction.date.startsWith(mois ?? ""))}
          mois={mois}
          peutReculer={indexMois > 0}
          peutAvancer={indexMois >= 0 && indexMois < moisDispo.length - 1}
          onReculer={() => mettreAJour({ mois: moisDispo[indexMois - 1] ?? null })}
          onAvancer={() => mettreAJour({ mois: moisDispo[indexMois + 1] ?? null })}
          sens={etat.sens}
          onSens={(sens) => mettreAJour({ sens })}
          onActualiser={reessayerOperations}
        />
      )}
      {toast && <ToastDecision libelle={toast.libelle} onAnnuler={toast.onAnnuler} />}
    </div>
  );
}

type CorrectionAffichee = {
  libelle: string;
  precedente: string;
  ecritureId: string;
};

function Entete({
  dossier,
  reste,
  onReessayer,
}: {
  dossier: { statut: "en_cours" } | { statut: "pret"; valeur: DossierResume } | { statut: "erreur"; message: string };
  /** Questions qui attendent encore une réponse ; `null` tant que les
   * opérations ne sont pas chargées. */
  reste: number | null;
  onReessayer: () => void;
}) {
  if (dossier.statut === "erreur") {
    return <Etat type="erreur" message={dossier.message} onReessayer={onReessayer} className="mt-0" />;
  }
  if (dossier.statut === "en_cours") {
    return (
      <Etat type="chargement" className="mt-0">
        <Squelette className="h-8 w-48" />
        <Squelette className="mt-2 h-4 w-40" />
        <Squelette className="mt-6 h-8 w-32" />
        <Squelette className="mt-2 h-4 w-56" />
      </Etat>
    );
  }
  const fiche = dossier.valeur;
  return (
    <>
      <h1 className="text-[28px] font-bold tracking-tight text-ink">{fiche.nom}</h1>
      <p className="mt-1 text-sm text-subtle">
        {fiche.forme_juridique} · {fiche.regime_libelle}
      </p>
      {reste !== null && (
        <p className="mt-6 text-[28px] font-bold leading-tight tracking-tight text-ink">
          {reste > 0 ? (
            <>
              Il reste{" "}
              <span className="bg-[linear-gradient(transparent_58%,var(--color-highlight)_58%)] px-0.5">
                {reste} {reste > 1 ? "questions" : "question"}
              </span>
              .
            </>
          ) : (
            "Tout est à jour."
          )}
        </p>
      )}
      <div className="mt-6">
        <ResultatACeJour dossier={fiche} />
      </div>
      <ConnexionBancaire peutConnecter={fiche.peut_connecter_sa_banque} />
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
      className={`inline-flex h-11 items-center rounded-full px-4 text-sm font-medium ${ANNEAU} ${
        actif ? "bg-ink text-canvas" : "text-subtle"
      }`}
    >
      {children}
    </button>
  );
}

function Arriere({
  courante,
  file,
  tickets,
  dossierId,
  suit,
  erreur,
  onChange,
  onChoisir,
  onGroupe,
  onVoirMouvements,
}: {
  courante: TransactionVue | null;
  file: TransactionVue[];
  tickets: TransactionVue[];
  dossierId: string;
  suit: boolean;
  erreur: string | null;
  onChange: (transaction: TransactionVue) => void;
  onChoisir: (transaction: TransactionVue, categorie: string, libelle: string) => void;
  onGroupe: (ids: string[], libelle: string) => void;
  onVoirMouvements: () => void;
}) {
  const zoneRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!suit) return;
    zoneRef.current?.focus({ preventScroll: true });
  }, [suit, courante?.ecriture_id]);

  if (!courante && tickets.length === 0) {
    return (
      <div ref={zoneRef} tabIndex={-1} role="region" aria-label="À traiter" className={`mt-6 outline-none ${ANNEAU}`}>
        <Etat
          type="vide"
          className="mt-0"
          message="Tout est à jour."
          action={{ libelle: "Voir mes mouvements", onClick: onVoirMouvements }}
        />
      </div>
    );
  }
  const groupe = courante ? groupeCourant(courante, file) : null;
  const proposition = courante?.proposition
    ? { code: courante.proposition, libelle: libelleCategorie(courante.proposition) }
    : null;
  const confirmableIci =
    proposition !== null && confirmable(proposition.code, courante?.origine_proposition ?? null);
  return (
    <div ref={zoneRef} tabIndex={-1} role="region" aria-label="À traiter" className={`outline-none ${ANNEAU}`}>
      {courante && (
        <div className="mt-4 border-b border-hairline pb-4">
          <LigneMontant
            nom={presenter(courante.libelle).nom}
            detail={proposition?.libelle ?? null}
            transaction={courante}
          />
          {ticketPrioritaire(courante) && (
            <AjouterTicketSortie dossierId={dossierId} transaction={courante} onJointe={onChange} />
          )}
          <div className="mt-3">
            {estRetrait(courante.proposition) ? (
              <QuestionRetrait
                key={courante.ecriture_id}
                erreur={erreur}
                onReponse={(categorie, libelle) => onChoisir(courante, categorie, libelle)}
              />
            ) : (
              <QuestionCategorisation
                key={courante.ecriture_id}
                proposition={confirmableIci ? proposition : null}
                origine={courante.origine_proposition}
                montantCts={courante.montant_cts}
                sansProposition={proposition === null}
                raccourci={confirmableIci}
                erreur={erreur}
                onReponse={(categorie, libelle) => onChoisir(courante, categorie, libelle)}
              />
            )}
          </div>
          {groupe && (
            <ConfirmationGroupee
              dossierId={dossierId}
              categorie={groupe[0]}
              libelle={libelleCategorie(groupe[0])}
              operations={groupe[1].map((operation) => ({
                ecritureId: operation.ecriture_id,
                nom: presenter(operation.libelle).nom,
                montantCts: operation.montant_cts,
              }))}
              onConfirme={() => onGroupe(groupe[1].map((operation) => operation.ecriture_id), libelleCategorie(groupe[0]))}
            />
          )}
        </div>
      )}
      <StationTickets dossierId={dossierId} depenses={tickets} onJointe={onChange} />
    </div>
  );
}

function groupeCourant(
  courante: TransactionVue,
  file: TransactionVue[],
): [string, TransactionVue[]] | null {
  return (
    groupesSemblables(file).find(([, operations]) =>
      operations.some((operation) => operation.ecriture_id === courante.ecriture_id),
    ) ?? null
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
  ouverte,
  enCours,
  erreur,
  onOuvrir,
  onChoisir,
  onJointe,
  transactions,
  mois,
  peutReculer,
  peutAvancer,
  onReculer,
  onAvancer,
  sens,
  onSens,
  onActualiser,
}: {
  dossierId: string;
  ouverte: string | null;
  enCours: boolean;
  erreur: string | null;
  onOuvrir: (ecritureId: string | null) => void;
  onChoisir: (transaction: TransactionVue, categorie: string, libelle: string) => void;
  onJointe: (transaction: TransactionVue) => void;
  transactions: TransactionVue[];
  mois: string | undefined;
  peutReculer: boolean;
  peutAvancer: boolean;
  onReculer: () => void;
  onAvancer: () => void;
  sens: SensActivite;
  onSens: (sens: SensActivite) => void;
  onActualiser: () => void;
}) {
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
        <Onglet actif={sens === "sorties"} onClick={() => onSens("sorties")}>
          Sorties
        </Onglet>
        <Onglet actif={sens === "entrees"} onClick={() => onSens("entrees")}>
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
        <Etat
          type="vide"
          message={sens === "sorties" ? "Aucune sortie ce mois-ci." : "Aucune entrée ce mois-ci."}
          action={actionMoisVide(
            sens,
            transactions,
            peutReculer,
            peutAvancer,
            onSens,
            onReculer,
            onAvancer,
            onActualiser,
          )}
        />
      ) : (
        jours.map(([jour, lignes]) => (
          <section key={jour} className="mt-6">
            <h2 className="text-sm font-medium text-subtle">{libelleJour(jour)}</h2>
            <ul>
              {lignes.map((transaction) => {
                const { nom, detail } = presenter(transaction.libelle);
                const estOuverte = ouverte === transaction.ecriture_id;
                const proposition = transaction.proposition
                  ? { code: transaction.proposition, libelle: libelleCategorie(transaction.proposition) }
                  : null;
                return (
                  <li key={transaction.ecriture_id} className="border-b border-hairline py-3">
                    <LigneMontant nom={nom} detail={detail} transaction={transaction} />
                    {transaction.reclassee_par && (
                      <p className="mt-1 text-sm text-subtle">
                        {phraseReclassement(transaction)}
                      </p>
                    )}
                    {sens === "sorties" && (
                      <AjouterTicketSortie
                        dossierId={dossierId}
                        transaction={transaction}
                        onJointe={onJointe}
                      />
                    )}
                    <button
                      type="button"
                      aria-expanded={estOuverte}
                      aria-label={`Corriger ${nom}`}
                      onClick={() => onOuvrir(estOuverte ? null : transaction.ecriture_id)}
                      className={`mt-1 min-h-11 rounded-md px-1 text-sm font-medium text-signal ${ANNEAU}`}
                    >
                      Corriger
                    </button>
                    {estOuverte && (
                      <div className="mt-3">
                        <QuestionCategorisation
                          corriger={transaction.statut === "validé"}
                          proposition={
                            proposition !== null &&
                            confirmable(proposition.code, transaction.origine_proposition)
                              ? proposition
                              : null
                          }
                          origine={transaction.origine_proposition}
                          montantCts={transaction.montant_cts}
                          sansProposition={proposition === null}
                          enCours={enCours}
                          erreur={erreur}
                          onReponse={(categorie, libelle) => onChoisir(transaction, categorie, libelle)}
                        />
                      </div>
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
      setErreur(
        phrasePourChauffeur(
          exception instanceof ApiError ? exception.message : "Échec de l'envoi de la photo.",
        ),
      );
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
        className={`mt-1 inline-flex min-h-11 items-center rounded-md px-1 text-sm font-medium text-signal disabled:opacity-50 ${ANNEAU}`}
      >
        {envoi ? "Envoi…" : "Ajouter un ticket"}
      </button>
      {erreur && <p className="mt-1 text-xs text-danger">{erreur}</p>}
    </div>
  );
}

/** AXE-800 : l'expert-comptable a reclassé l'opération ; le chauffeur voit
 * qui, quand et pourquoi. */
function phraseReclassement(transaction: TransactionVue): string {
  const quand = transaction.reclassee_le ? ` le ${formatDate(transaction.reclassee_le)}` : "";
  const pourquoi = transaction.motif_reclassement ? ` : ${transaction.motif_reclassement}` : "";
  return `Reclassée par ${transaction.reclassee_par}${quand}${pourquoi}`;
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
        {phraseTvaLigne(transaction)}
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

function phraseTvaLigne(transaction: TransactionVue) {
  if (transaction.montant_cts >= 0) return null;
  const phrase = phraseTva(
    transaction.tva_estimee_cts,
    transaction.tva_relevee_cts,
    transaction.montant_cts,
    !transaction.a_justificatif,
  );
  return phrase ? <span className="mt-0.5 block text-sm text-subtle">{phrase}</span> : null;
}

/** Le bouton reste inactif. L'explication est un texte : un `title` ne se lit pas au doigt. */
function ConnexionBancaire({ peutConnecter }: { peutConnecter: boolean }) {
  if (!peutConnecter) return null;
  return (
    <div className="mt-6">
      <Button
        type="button"
        variant="secondary"
        className="h-11 w-full"
        disabled
        aria-describedby="connexion-banque-bientot"
      >
        Connecter ma banque
      </Button>
      <p id="connexion-banque-bientot" className="mt-2 text-sm text-subtle">
        Bientôt disponible.
      </p>
    </div>
  );
}

function actionMoisVide(
  sens: SensActivite,
  transactions: TransactionVue[],
  peutReculer: boolean,
  peutAvancer: boolean,
  onSens: (sens: SensActivite) => void,
  onReculer: () => void,
  onAvancer: () => void,
  onActualiser: () => void,
): { libelle: string; onClick: () => void } {
  const autre = sens === "sorties" ? "entrees" : "sorties";
  const aLAutre = transactions.some((transaction) =>
    autre === "sorties" ? transaction.montant_cts < 0 : transaction.montant_cts > 0,
  );
  if (aLAutre) {
    return {
      libelle: autre === "sorties" ? "Voir les sorties" : "Voir les entrées",
      onClick: () => onSens(autre),
    };
  }
  if (peutReculer) return { libelle: "Mois précédent", onClick: onReculer };
  if (peutAvancer) return { libelle: "Mois suivant", onClick: onAvancer };
  return { libelle: "Actualiser", onClick: onActualiser };
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
