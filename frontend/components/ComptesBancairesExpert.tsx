"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  ModeExpertRefuse,
  deciderCompteBancaireExpert,
  lireComptesBancairesExpert,
} from "@/lib/auth-gestionnaire";
import { choixCompte, estNonVentile, phraseFiche, titreCompte } from "@/lib/comptes-bancaires";
import type { CompteBancaireVue } from "@/lib/types";

type Etat =
  | { statut: "en_cours" }
  | { statut: "refuse" }
  | { statut: "erreur"; message: string }
  | { statut: "pret"; comptes: CompteBancaireVue[] };

const LIBELLE_CHOIX = {
  retenu: "Compte de l'activité",
  ecarte: "Compte personnel",
  a_decider: "À décider",
} as const;

/** AXE-956 : dans la fiche d'une entreprise, l'expert-comptable habilité
 * retient ou écarte un compte bancaire à la place du dirigeant. Un
 * gestionnaire non expert ne voit pas les comptes (doc 19 §2.4). */
export function ComptesBancairesExpert({
  dossierId,
  phraseAttente,
  onDecide,
}: {
  dossierId: string;
  /** « Un compte bancaire attend le choix du dirigeant… », ou `null`. */
  phraseAttente: string | null;
  onDecide: () => void;
}) {
  const [etat, setEtat] = useState<Etat>({ statut: "en_cours" });
  const [enCours, setEnCours] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(() => {
    setEtat({ statut: "en_cours" });
    lireComptesBancairesExpert(dossierId)
      .then((comptes) => setEtat({ statut: "pret", comptes }))
      .catch((exception) =>
        setEtat(
          exception instanceof ModeExpertRefuse
            ? { statut: "refuse" }
            : { statut: "erreur", message: "Les comptes n'ont pas pu être lus." },
        ),
      );
  }, [dossierId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    charger();
  }, [charger]);

  async function decider(compte: string, retenu: boolean) {
    setEnCours(compte);
    setErreur(null);
    try {
      setEtat({ statut: "pret", comptes: await deciderCompteBancaireExpert(dossierId, compte, retenu) });
      onDecide();
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Le choix n'a pas pu être enregistré.");
    } finally {
      setEnCours(null);
    }
  }

  // Sans compte en attente, un gestionnaire non expert n'a rien à voir ici.
  if (etat.statut === "refuse" && !phraseAttente) return null;
  if (etat.statut === "en_cours" && !phraseAttente) return null;
  return (
    <section className="mt-5 border-t border-border pt-4" aria-labelledby="titre-comptes-fiche">
      <h3 id="titre-comptes-fiche" className="text-sm font-medium text-ink">
        Comptes bancaires
      </h3>
      {phraseAttente && <p className="mt-1 text-sm text-subtle">{phraseAttente}</p>}
      {etat.statut === "refuse" && (
        <p className="mt-1 text-sm text-subtle">
          Le dirigeant répond dans son espace, ou l&apos;expert-comptable du portefeuille depuis
          cette fiche.
        </p>
      )}
      {etat.statut === "erreur" && (
        <p className="mt-2 text-sm text-danger">
          {etat.message}{" "}
          <button type="button" className="underline" onClick={charger}>
            Réessayer
          </button>
        </p>
      )}
      {etat.statut === "pret" && (
        <ListeComptes
          comptes={etat.comptes.filter((compte) => !estNonVentile(compte))}
          enCours={enCours}
          erreur={erreur}
          decider={decider}
        />
      )}
    </section>
  );
}

function ListeComptes({
  comptes,
  enCours,
  erreur,
  decider,
}: {
  comptes: CompteBancaireVue[];
  enCours: string | null;
  erreur: string | null;
  decider: (compte: string, retenu: boolean) => void;
}) {
  if (comptes.length === 0) {
    return <p className="mt-2 text-sm text-subtle">Aucun compte bancaire relevé.</p>;
  }
  return (
    <>
      <ul className="mt-2 divide-y divide-hairline">
        {comptes.map((compte) => {
          const choix = choixCompte(compte);
          const fiche = phraseFiche(compte);
          const propose = choix === "a_decider" ? compte.propose_par_fiche : null;
          return (
            <li key={compte.compte} className="py-2.5">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-sm text-ink">
                  {titreCompte(compte)}
                  <span className="ml-2 text-xs text-subtle">{compte.compte}</span>
                </span>
                <span
                  className={`shrink-0 text-xs ${choix === "a_decider" ? "font-medium text-warning" : "text-subtle"}`}
                >
                  {LIBELLE_CHOIX[choix]}
                </span>
              </div>
              {fiche && <p className="mt-1 text-xs text-subtle">{fiche}</p>}
              {choix !== "retenu" && (
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant={propose === true ? "primary" : "secondary"}
                    size="sm"
                    disabled={enCours !== null}
                    onClick={() => decider(compte.compte, true)}
                  >
                    Sert à l&apos;activité
                  </Button>
                  {choix === "a_decider" && (
                    <Button
                      type="button"
                      variant={propose === false ? "primary" : "ghost"}
                      size="sm"
                      disabled={enCours !== null}
                      onClick={() => decider(compte.compte, false)}
                    >
                      Compte personnel
                    </Button>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
      <p className="mt-2 text-xs text-subtle">
        Votre choix vaut celui du dirigeant et il est tracé à votre nom. Un compte retenu voit son
        historique importé à la prochaine synchronisation.
      </p>
      {erreur && <p className="mt-2 text-sm text-danger">{erreur}</p>}
    </>
  );
}
