"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { lancerSynchronisation, lireSynchronisation } from "@/lib/auth-gestionnaire";
import { formatDate } from "@/lib/format";
import { phraseSynchro, synchroEnCours } from "@/lib/synchronisation";
import type { Synchronisation } from "@/lib/types";

const RELECTURE_MS = 3000;

/** État de la synchronisation Digifactory (AXE-845). Elle tourne en
 * arrière-plan : la page reste utilisable, l'état se relit toutes les 3 s
 * tant qu'elle n'est pas finie. Les nouveaux contacts arrivent dans Imports. */
export function useSynchronisationPortefeuille(onTerminee: () => void) {
  const [synchro, setSynchro] = useState<Synchronisation | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  const relire = useCallback(() => {
    lireSynchronisation().then(setSynchro).catch(() => setSynchro(null));
  }, []);

  useEffect(relire, [relire]);

  const enCours = synchroEnCours(synchro);
  useEffect(() => {
    if (!enCours) return;
    const minuterie = window.setInterval(() => {
      lireSynchronisation()
        .then((suivante) => {
          setSynchro(suivante);
          if (!synchroEnCours(suivante)) onTerminee();
        })
        .catch(() => undefined);
    }, RELECTURE_MS);
    return () => window.clearInterval(minuterie);
  }, [enCours, onTerminee]);

  function lancer() {
    setErreur(null);
    lancerSynchronisation()
      .then(setSynchro)
      .catch((exception) => setErreur(exception instanceof Error ? exception.message : "Erreur."));
  }

  return { synchro, erreur, enCours, lancer };
}

export type SynchronisationEtat = ReturnType<typeof useSynchronisationPortefeuille>;

/** Bouton « Synchroniser » : le bouton principal de l'écran (encre). */
export function BoutonSynchroniser({ etat }: { etat: SynchronisationEtat }) {
  return (
    <Button type="button" disabled={etat.enCours} onClick={etat.lancer}>
      {etat.enCours ? "Synchronisation…" : "Synchroniser"}
    </Button>
  );
}

/** Dernière synchronisation, ou son échec, en une phrase. */
export function PhraseSynchronisation({ etat }: { etat: SynchronisationEtat }) {
  const phrase = phraseSynchro(etat.synchro, formatDate);
  const enEchec = etat.synchro?.statut === "echec" || etat.erreur !== null;
  const texte = etat.erreur ?? phrase;
  if (!texte) return null;
  return (
    <p role={enEchec ? "alert" : "status"} className={`text-[13px] ${enEchec ? "text-danger" : "text-muted"}`}>
      {texte}
    </p>
  );
}
