"use client";

import { useCallback, useEffect, useState } from "react";

import { Etat } from "@/components/Etat";
import { Squelette } from "@/components/Squelette";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  ErreurAuthChauffeur,
  deciderCompteBancaireChauffeur,
  listerComptesBancairesChauffeur,
} from "@/lib/auth-chauffeur";
import { choixCompte, estNonVentile, rapprochement, titreCompte } from "@/lib/comptes-bancaires";
import { formatDate, formatMontant } from "@/lib/format";
import type { CompteBancaireVue } from "@/lib/types";

type Etat_ =
  | { statut: "en_cours" }
  | { statut: "erreur"; message: string }
  | { statut: "pret"; comptes: CompteBancaireVue[] };

/** AXE-832 : chaque compte bancaire, son solde dans la comptabilité et celui
 * de la banque, côte à côte. Un écart se voit en rouge. */
export function ComptesBancaires({ dossierId }: { dossierId: string }) {
  const [etat, setEtat] = useState<Etat_>({ statut: "en_cours" });

  const charger = useCallback(() => {
    setEtat({ statut: "en_cours" });
    listerComptesBancairesChauffeur(dossierId)
      .then((comptes) => setEtat({ statut: "pret", comptes }))
      .catch(() => setEtat({ statut: "erreur", message: "Vos comptes n'ont pas pu être lus." }));
  }, [dossierId]);

  useEffect(() => {
    // Premier chargement, comme les autres blocs de l'écran.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    charger();
  }, [charger]);

  return (
    <section className="mb-8" aria-labelledby="titre-comptes-bancaires">
      <h2 id="titre-comptes-bancaires" className="text-base font-semibold text-ink">
        Mes comptes bancaires
      </h2>
      {etat.statut === "en_cours" && (
        <Etat type="chargement" className="mt-3">
          <Squelette className="h-12 w-full" />
          <Squelette className="mt-2 h-12 w-full" />
        </Etat>
      )}
      {etat.statut === "erreur" && (
        <Etat type="erreur" message={etat.message} onReessayer={charger} className="mt-3" />
      )}
      {etat.statut === "pret" && etat.comptes.length === 0 && (
        <p className="mt-3 text-sm text-subtle">
          Aucun compte bancaire relié pour l&apos;instant. Ils apparaîtront après la prochaine
          synchronisation de votre banque.
        </p>
      )}
      {etat.statut === "pret" && etat.comptes.length > 0 && (
        <ul className="mt-3 divide-y divide-hairline">
          {etat.comptes.map((compte) => (
            <LigneCompte
              key={compte.compte}
              dossierId={dossierId}
              compte={compte}
              onDecide={(comptes) => setEtat({ statut: "pret", comptes })}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function LigneCompte({
  dossierId,
  compte,
  onDecide,
}: {
  dossierId: string;
  compte: CompteBancaireVue;
  onDecide: (comptes: CompteBancaireVue[]) => void;
}) {
  const etat = rapprochement(compte);
  const choix = choixCompte(compte);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  async function decider(retenu: boolean) {
    setEnCours(true);
    setErreur(null);
    try {
      onDecide(await deciderCompteBancaireChauffeur(dossierId, compte.compte, retenu));
    } catch (exception) {
      setErreur(
        exception instanceof ErreurAuthChauffeur || exception instanceof ApiError
          ? exception.message
          : "Votre choix n'a pas pu être enregistré.",
      );
    } finally {
      setEnCours(false);
    }
  }

  if (choix !== "retenu") {
    return (
      <li className="py-3">
        <span className="text-sm font-medium text-ink">{titreCompte(compte)}</span>
        <p className="mt-1 text-sm text-subtle">
          {choix === "a_decider"
            ? "Ce compte sert-il à votre activité ? Tant que vous n'avez pas répondu, ses opérations ne sont pas comptées."
            : "Compte personnel : ses opérations ne sont pas comptées."}
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          <Button type="button" variant="secondary" className="min-h-11" disabled={enCours} onClick={() => decider(true)}>
            Oui, compte de l&apos;activité
          </Button>
          {choix === "a_decider" && (
            <Button type="button" variant="secondary" className="min-h-11" disabled={enCours} onClick={() => decider(false)}>
              Non, compte personnel
            </Button>
          )}
        </div>
        {erreur && <p className="mt-1 text-xs text-danger">{erreur}</p>}
      </li>
    );
  }

  return (
    <li className="py-3">
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-sm font-medium text-ink">{titreCompte(compte)}</span>
        <span className="text-sm tabular-nums text-ink">
          {formatMontant(compte.solde_comptable_cts)}
        </span>
      </div>
      <p className="mt-1 text-xs text-subtle">
        {etat.etat === "a_jour" &&
          `Identique au solde de la banque${compte.releve_le ? ` du ${formatDate(compte.releve_le)}` : ""}.`}
        {etat.etat === "jamais_releve" && "Solde de la banque pas encore relevé."}
        {etat.etat === "non_ventile" &&
          "Opérations enregistrées avant que vos comptes soient distingués."}
        {etat.etat === "ecart" && (
          <span className="text-danger">
            Écart de {formatMontant(etat.ecartCts)} avec la banque (
            {formatMontant(compte.solde_banque_cts ?? 0)}).
          </span>
        )}
      </p>
      {!estNonVentile(compte) && (
        <button
          type="button"
          className="mt-1 min-h-11 text-xs font-medium text-signal underline-offset-2 hover:underline"
          disabled={enCours}
          onClick={() => decider(false)}
        >
          C&apos;est un compte personnel
        </button>
      )}
      {erreur && <p className="mt-1 text-xs text-danger">{erreur}</p>}
    </li>
  );
}
