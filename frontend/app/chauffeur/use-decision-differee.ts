"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { DELAI_ANNULATION_MS } from "@/app/chauffeur/file-a-traiter";
import { ApiError } from "@/lib/api";
import { trancherTransactionChauffeur } from "@/lib/auth-chauffeur";
import type { TransactionVue } from "@/lib/types";

export type DecisionEnAttente = {
  original: TransactionVue;
  categorie: string;
  libelle: string;
};

/** La décision part après un court délai. « Annuler » la retire avant l'envoi.
 * Quitter la page l'envoie tout de suite : elle ne reste pas en suspens. */
export function useDecisionDifferee(
  dossierId: string,
  onEnregistree: (transaction: TransactionVue) => void,
  onEchec: (original: TransactionVue, message: string) => void,
): {
  enAttente: DecisionEnAttente | null;
  poser: (decision: DecisionEnAttente) => void;
  annuler: () => DecisionEnAttente | null;
} {
  const [enAttente, setEnAttente] = useState<DecisionEnAttente | null>(null);
  const enAttenteRef = useRef<DecisionEnAttente | null>(null);
  const timer = useRef<number | null>(null);
  const monte = useRef(true);
  const onEnregistreeRef = useRef(onEnregistree);
  const onEchecRef = useRef(onEchec);
  useEffect(() => {
    onEnregistreeRef.current = onEnregistree;
    onEchecRef.current = onEchec;
  }, [onEchec, onEnregistree]);

  const envoyer = useCallback(
    (decision: DecisionEnAttente) => {
      trancherTransactionChauffeur(dossierId, decision.original.ecriture_id, decision.categorie)
        .then((transaction) => onEnregistreeRef.current(transaction))
        .catch((exception: unknown) => {
          const message = exception instanceof ApiError ? exception.message : "Échec de l'envoi.";
          onEchecRef.current(decision.original, message);
        });
    },
    [dossierId],
  );

  const consommer = useCallback((): DecisionEnAttente | null => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
    const decision = enAttenteRef.current;
    enAttenteRef.current = null;
    if (monte.current) setEnAttente(null);
    return decision;
  }, []);

  const envoyerCourante = useCallback(() => {
    const decision = consommer();
    if (decision) envoyer(decision);
  }, [consommer, envoyer]);

  const poser = useCallback(
    (decision: DecisionEnAttente) => {
      envoyerCourante();
      enAttenteRef.current = decision;
      setEnAttente(decision);
      timer.current = window.setTimeout(envoyerCourante, DELAI_ANNULATION_MS);
    },
    [envoyerCourante],
  );

  const annuler = useCallback(() => consommer(), [consommer]);

  useEffect(() => {
    monte.current = true;
    const auDepart = () => envoyerCourante();
    window.addEventListener("pagehide", auDepart);
    return () => {
      monte.current = false;
      window.removeEventListener("pagehide", auDepart);
      envoyerCourante();
    };
  }, [envoyerCourante]);

  return { enAttente, poser, annuler };
}
