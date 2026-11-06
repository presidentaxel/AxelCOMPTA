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

/** Bouton « Synchroniser » et nouveaux chauffeurs Digifactory (AXE-845).
 * La synchro tourne en arrière-plan : la page reste utilisable, l'état se
 * relit toutes les 3 s tant qu'elle n'est pas finie. */
export function SynchronisationPortefeuille({
  ecriture,
  onTerminee,
}: {
  ecriture: boolean;
  onTerminee: () => void;
}) {
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

  const proposes = aValider(contacts);
  const evidents = chauffeursEvidents(contacts);
  const ecartes = ignores(contacts);
  const enCreation = contacts.filter((c) => c.decision === "ajouter");
  const phrase = phraseSynchro(synchro, formatDate);

  return (
    <section className="mt-6">
      <div className="flex flex-wrap items-center gap-3">
        {ecriture && (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={enCours}
            onClick={() => {
              setErreur(null);
              lancerSynchronisation()
                .then(setSynchro)
                .catch((exception) =>
                  setErreur(exception instanceof Error ? exception.message : "Erreur."),
                );
            }}
          >
            {enCours ? "Synchronisation…" : "Synchroniser"}
          </Button>
        )}
        {phrase && (
          <span className={`text-sm ${synchro?.statut === "echec" ? "text-danger" : "text-subtle"}`}>
            {phrase}
          </span>
        )}
      </div>
      {erreur && <p className="mt-2 text-sm text-danger">{erreur}</p>}
      {(proposes.length > 0 || enCreation.length > 0) && (
        <div className="mt-4 rounded-lg border border-border bg-canvas p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-ink">Nouveaux chauffeurs Digifactory</h2>
            {ecriture && evidents.length > 1 && (
              <Button type="button" size="sm" onClick={() => decider(evidents.map((c) => c.contact_nr), "ajouter")}>
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
                      <Button type="button" size="sm" onClick={() => decider([contact.contact_nr], "ajouter")}>
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
        </div>
      )}
    </section>
  );
}
