"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { fetchAvecAuthChauffeur, obtenirSession } from "@/lib/auth-chauffeur";
import type { DossierResume, TransactionVue } from "@/lib/types";

export type Bloc<T> =
  | { statut: "en_cours" }
  | { statut: "pret"; valeur: T }
  | { statut: "erreur"; message: string };

/** Vrai si la session ouvre ce dossier. Sinon, renvoie vers la connexion ou
 * vers le dossier du chauffeur : une autre adresse que la sienne ne charge rien. */
function sessionOuvreLeDossier(dossierId: string, router: ReturnType<typeof useRouter>): boolean {
  const session = obtenirSession();
  if (session === null) {
    router.push("/chauffeur/login");
    return false;
  }
  if (session.dossierId !== dossierId) {
    router.replace(`/chauffeur/${session.dossierId}`);
    return false;
  }
  return true;
}

/** Charge le résumé du dossier du chauffeur connecté. Les opérations ont
 * leur propre chargement (`useOperationsChauffeur`) : les écrans qui n'en ont
 * pas besoin, comme Exercice et Compte, ne les demandent pas.
 * `recharger` relit la fiche sans remettre le squelette (après une clôture,
 * les chiffres et la période changent). */
export function useDossierChauffeur(dossierId: string): {
  dossier: Bloc<DossierResume>;
  recharger: () => void;
} {
  const router = useRouter();
  const [dossier, setDossier] = useState<Bloc<DossierResume>>({ statut: "en_cours" });
  const [cle, setCle] = useState(dossierId);
  if (cle !== dossierId) {
    setCle(dossierId);
    setDossier({ statut: "en_cours" });
  }

  useEffect(() => {
    if (!sessionOuvreLeDossier(dossierId, router)) return;
    let annule = false;
    fetchAvecAuthChauffeur<DossierResume>(`/dossiers/${dossierId}`)
      .then((valeur) => {
        if (!annule) setDossier({ statut: "pret", valeur });
      })
      .catch(() => {
        if (!annule) setDossier({ statut: "erreur", message: "Impossible de charger le dossier." });
      });
    return () => {
      annule = true;
    };
  }, [dossierId, router]);

  function recharger() {
    fetchAvecAuthChauffeur<DossierResume>(`/dossiers/${dossierId}`)
      .then((valeur) => setDossier({ statut: "pret", valeur }))
      .catch(() => undefined);
  }

  return { dossier, recharger };
}

/** Charge les opérations du dossier. Seul l'écran Activité s'en sert.
 * `remplacer` met à jour une opération déjà affichée (photo, réponse) sans
 * recharger la page. */
export function useOperationsChauffeur(dossierId: string): {
  transactions: Bloc<TransactionVue[]>;
  remplacer: (transaction: TransactionVue) => void;
  recharger: () => void;
} {
  const router = useRouter();
  const [transactions, setTransactions] = useState<Bloc<TransactionVue[]>>({ statut: "en_cours" });
  const [cle, setCle] = useState(dossierId);
  if (cle !== dossierId) {
    setCle(dossierId);
    setTransactions({ statut: "en_cours" });
  }

  useEffect(() => {
    if (!sessionOuvreLeDossier(dossierId, router)) return;
    let annule = false;
    fetchAvecAuthChauffeur<TransactionVue[]>(`/dossiers/${dossierId}/transactions`)
      .then((valeur) => {
        if (!annule) setTransactions({ statut: "pret", valeur });
      })
      .catch(() => {
        if (!annule) {
          setTransactions({ statut: "erreur", message: "Impossible de charger les opérations." });
        }
      });
    return () => {
      annule = true;
    };
  }, [dossierId, router]);

  function remplacer(transaction: TransactionVue) {
    setTransactions((etat) =>
      etat.statut === "pret"
        ? {
            ...etat,
            valeur: etat.valeur.map((ligne) =>
              ligne.ecriture_id === transaction.ecriture_id ? transaction : ligne,
            ),
          }
        : etat,
    );
  }

  /** Relit les opérations sans remettre la liste en squelette : après une
   * décision, les propositions des opérations semblables changent. */
  function recharger() {
    fetchAvecAuthChauffeur<TransactionVue[]>(`/dossiers/${dossierId}/transactions`)
      .then((valeur) =>
        setTransactions((etat) => (etat.statut === "pret" ? { statut: "pret", valeur } : etat)),
      )
      .catch(() => undefined);
  }

  return { transactions, remplacer, recharger };
}
