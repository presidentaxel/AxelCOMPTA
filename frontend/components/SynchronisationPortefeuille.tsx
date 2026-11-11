"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  deciderNouveauxChauffeurs,
  lancerSynchronisation,
  lireSynchronisation,
  listerNouveauxChauffeurs,
} from "@/lib/auth-gestionnaire";
import { formatDate } from "@/lib/format";
import {
  aValider,
  chauffeursEvidents,
  ignores,
  phraseSynchro,
  synchroEnCours,
} from "@/lib/synchronisation";
import type { NouveauChauffeur, Synchronisation } from "@/lib/types";

const RELECTURE_MS = 3000;

/** État de la synchronisation et des nouveaux chauffeurs Digifactory (AXE-845).
 * La synchro tourne en arrière-plan : la page reste utilisable, l'état se
 * relit toutes les 3 s tant qu'elle n'est pas finie.
 *
 * C'est un hook, et non un composant, pour que le bouton « Synchroniser »
 * (dans l'en-tête de l'écran, à côté d'« Importer ») et la liste des nouveaux
 * chauffeurs (plus bas) partagent un seul état et une seule relecture. */
export function useSynchronisationPortefeuille(onTerminee: () => void) {
  const [synchro, setSynchro] = useState<Synchronisation | null>(null);
  const [contacts, setContacts] = useState<NouveauChauffeur[]>([]);
  const [erreur, setErreur] = useState<string | null>(null);

  const relire = useCallback(() => {
    lireSynchronisation().then(setSynchro).catch(() => setSynchro(null));
    listerNouveauxChauffeurs().then(setContacts).catch(() => setContacts([]));
  }, []);

  useEffect(relire, [relire]);

  const enCours = synchroEnCours(synchro);
  useEffect(() => {
    if (!enCours) return;
    const minuterie = window.setInterval(() => {
      lireSynchronisation()
        .then((suivante) => {
          setSynchro(suivante);
          if (!synchroEnCours(suivante)) {
            listerNouveauxChauffeurs().then(setContacts).catch(() => undefined);
            onTerminee();
          }
        })
        .catch(() => undefined);
    }, RELECTURE_MS);
    return () => window.clearInterval(minuterie);
  }, [enCours, onTerminee]);

  function decider(numeros: string[], decision: "ajouter" | "ignorer" | "reprendre") {
    setErreur(null);
    deciderNouveauxChauffeurs(numeros, decision)
      .then((suivants) => {
        setContacts(suivants);
        if (decision === "ajouter") relire();
      })
      .catch((exception) => setErreur(exception instanceof Error ? exception.message : "Erreur."));
  }

  function lancer() {
    setErreur(null);
    lancerSynchronisation()
      .then(setSynchro)
      .catch((exception) => setErreur(exception instanceof Error ? exception.message : "Erreur."));
  }

  return { synchro, contacts, erreur, enCours, decider, lancer };
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

/** Nouveaux chauffeurs Digifactory à ajouter ou ignorer. Les boutons
 * d'ajout sont secondaires : le seul bouton principal de l'écran est
 * « Synchroniser ». */
export function NouveauxChauffeurs({
  etat,
  ecriture,
}: {
  etat: SynchronisationEtat;
  ecriture: boolean;
}) {
  const { contacts, decider } = etat;
  const proposes = aValider(contacts);
  const evidents = chauffeursEvidents(contacts);
  const ecartes = ignores(contacts);
  const enCreation = contacts.filter((c) => c.decision === "ajouter");

  if (proposes.length === 0 && enCreation.length === 0) return null;
  return (
    <section className="mt-6 rounded-lg border border-border bg-canvas p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">Nouveaux chauffeurs Digifactory</h2>
        {ecriture && evidents.length > 1 && (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => decider(evidents.map((c) => c.contact_nr), "ajouter")}
          >
            Ajouter les {evidents.length} chauffeurs VTC
          </Button>
        )}
      </div>
      <ul className="mt-2">
        {proposes.map((contact) => (
          <li key={contact.contact_nr} className="border-b border-hairline py-2 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium text-ink">{contact.nom}</span>
              {ecriture && (
                <span className="flex gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => decider([contact.contact_nr], "ajouter")}
                  >
                    Ajouter
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => decider([contact.contact_nr], "ignorer")}
                  >
                    Ignorer
                  </Button>
                </span>
              )}
            </div>
            <p className="mt-1 text-xs text-subtle">
              {[
                contact.forme,
                contact.exercice_debut ? `exercice au ${formatDate(contact.exercice_debut)}` : null,
                contact.code_naf ? `NAF ${contact.code_naf}` : null,
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
            {contact.avertissements.map((avertissement) => (
              <p key={avertissement} className="mt-1 text-xs text-warning">
                {avertissement}
              </p>
            ))}
          </li>
        ))}
        {enCreation.map((contact) => (
          <li key={contact.contact_nr} className="py-2 text-sm text-subtle">
            {contact.nom} : dossier en cours de création
          </li>
        ))}
      </ul>
      {ecartes.length > 0 && (
        <details className="mt-2 text-sm">
          <summary className="cursor-pointer text-subtle">Ignorés ({ecartes.length})</summary>
          <ul className="mt-1">
            {ecartes.map((contact) => (
              <li key={contact.contact_nr} className="flex items-center justify-between py-1">
                <span>{contact.nom}</span>
                {ecriture && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => decider([contact.contact_nr], "reprendre")}
                  >
                    Reprendre
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
