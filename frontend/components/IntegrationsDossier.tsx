"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  choisirBranchementDossier,
  lireAvancementRollee,
  lireBranchementsDossier,
  listerBranchements,
  synchroniserRollee,
  type Branchement,
} from "@/lib/auth-gestionnaire";
import { ORDRE_TYPES, TYPES_BRANCHEMENT } from "@/lib/branchements";

/** AXE-872 : l'accès qu'une entreprise utilise, pour chaque intégration qui
 * en a plusieurs. Rollee n'a pas de menu : le bouton lit tous les comptes
 * et relit Uber, Bolt… La phrase sous le bouton dit où en est la lecture. */
export function IntegrationsDossier({
  dossierId,
  admin,
  ecriture,
  onSynchronise,
}: {
  dossierId: string;
  admin: boolean;
  ecriture: boolean;
  onSynchronise: () => void;
}) {
  const [branchements, setBranchements] = useState<Branchement[]>([]);
  const [choix, setChoix] = useState<Record<string, string>>({});
  const [erreur, setErreur] = useState<string | null>(null);
  const [synchro, setSynchro] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const enCoursRef = useRef(false);

  useEffect(() => {
    let actif = true;
    Promise.all([listerBranchements(), lireBranchementsDossier(dossierId)])
      .then(([liste, lus]) => {
        if (!actif) return;
        setBranchements(liste);
        setChoix(lus);
      })
      .catch(() => {
        // Non lus : le bloc reste caché, l'entreprise garde les accès par défaut.
      });
    return () => {
      actif = false;
    };
  }, [dossierId]);

  const ficheRelue = useRef(false);
  const surSynchro = useRef(onSynchronise);
  useEffect(() => {
    surSynchro.current = onSynchronise;
  }, [onSynchronise]);
  useEffect(() => {
    if (!enCours) return;
    ficheRelue.current = false;
    let actif = true;
    const lire = () => {
      void lireAvancementRollee(dossierId).then((phrase) => {
        if (!actif || !enCoursRef.current || !phrase) return;
        setSynchro(phrase);
        if (
          !ficheRelue.current &&
          (phrase.includes("Reliez") || phrase.includes("lien est posé"))
        ) {
          ficheRelue.current = true;
          surSynchro.current();
        }
      });
    };
    const id = setInterval(lire, 2000);
    return () => {
      actif = false;
      clearInterval(id);
    };
  }, [enCours, dossierId]);

  const types = ORDRE_TYPES.filter(
    (type) =>
      type !== "rollee" && branchements.filter((b) => b.type === type && b.actif).length > 1,
  );
  if (types.length === 0 && !ecriture) return null;

  async function synchroniser() {
    setErreur(null);
    setSynchro(null);
    setEnCours(true);
    enCoursRef.current = true;
    try {
      const phrase = await synchroniserRollee(dossierId);
      enCoursRef.current = false;
      setSynchro(phrase);
      onSynchronise();
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Rollee n'a pas répondu.");
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div className="mt-4">
      {types.length > 0 && (
      <>
      <p className="text-sm font-medium text-ink">Intégrations utilisées</p>
      <dl className="mt-2 space-y-2">
        {types.map((type) => {
          const actifs = branchements.filter((b) => b.type === type && b.actif);
          const sansDefaut = type === "rollee";
          const defaut = actifs.find((b) => b.par_defaut);
          return (
            <div key={type} className="space-y-1">
              <dt className="text-sm text-subtle">
                {TYPES_BRANCHEMENT[type].nom}
              </dt>
              <dd>
                <select
                  aria-label={`Accès ${TYPES_BRANCHEMENT[type].nom} de cette entreprise`}
                  disabled={!admin}
                  value={choix[type] ?? ""}
                  onChange={async (evenement) => {
                    setErreur(null);
                    try {
                      setChoix(
                        await choisirBranchementDossier(
                          dossierId,
                          type,
                          evenement.target.value || null,
                        ),
                      );
                    } catch (exception) {
                      setErreur(
                        exception instanceof Error
                          ? exception.message
                          : "Choix non enregistré.",
                      );
                    }
                  }}
                  className="w-full rounded-md border border-border bg-canvas px-2 py-1 text-sm text-ink"
                >
                  <option value="">
                    {sansDefaut
                      ? "Pas encore relié, on interroge tous"
                      : `Par défaut${defaut ? ` (${defaut.nom})` : ""}`}
                  </option>
                  {actifs
                    .filter((b) => sansDefaut || !b.par_defaut)
                    .map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.nom}
                      </option>
                    ))}
                </select>
              </dd>
            </div>
          );
        })}
      </dl>
      </>
      )}
      {ecriture && (
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="mt-3"
          disabled={enCours}
          onClick={() => void synchroniser()}
        >
          {enCours ? "Synchronisation…" : "Synchroniser Rollee"}
        </Button>
      )}
      {synchro && <p className="mt-2 text-sm text-subtle">{synchro}</p>}
      {erreur && <p className="mt-2 text-sm text-danger">{erreur}</p>}
    </div>
  );
}
