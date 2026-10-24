"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { fetchAvecAuthChauffeur, obtenirSession } from "@/lib/auth-chauffeur";
import type { DossierResume, TransactionVue } from "@/lib/types";

export type Bloc<T> =
  | { statut: "en_cours" }
  | { statut: "pret"; valeur: T }
  | { statut: "erreur"; message: string };

/** Charge le dossier du chauffeur connecté. Le résumé et les opérations
 * arrivent chacun à leur tour : l'un n'attend pas l'autre. Une autre
 * adresse que la sienne renvoie vers son dossier. `remplacer` met à jour
 * une opération déjà affichée (photo, réponse) sans recharger la page. */
export function useDossierChauffeur(dossierId: string): {
  dossier: Bloc<DossierResume>;
  transactions: Bloc<TransactionVue[]>;
  remplacer: (transaction: TransactionVue) => void;
  recharger: () => void;
} {
  const router = useRouter();
  const [dossier, setDossier] = useState<Bloc<DossierResume>>({ statut: "en_cours" });
  const [transactions, setTransactions] = useState<Bloc<TransactionVue[]>>({ statut: "en_cours" });
  const [cle, setCle] = useState(dossierId);
  if (cle !== dossierId) {
    setCle(dossierId);
    setDossier({ statut: "en_cours" });
    setTransactions({ statut: "en_cours" });
  }

  useEffect(() => {
    const session = obtenirSession();
    if (session === null) {
      router.push("/chauffeur/login");
      return;
    }
    if (session.dossierId !== dossierId) {
      router.replace(`/chauffeur/${session.dossierId}`);
      return;
    }
    let annule = false;
    fetchAvecAuthChauffeur<DossierResume>(`/dossiers/${dossierId}`)
      .then((valeur) => {
        if (!annule) setDossier({ statut: "pret", valeur });
      })
      .catch(() => {
        if (!annule) setDossier({ statut: "erreur", message: "Impossible de charger le dossier." });
      });
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

  return { dossier, transactions, remplacer, recharger };
}
