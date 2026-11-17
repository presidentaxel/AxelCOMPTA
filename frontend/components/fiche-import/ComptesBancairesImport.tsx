"use client";

import { LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { comptesDigifactoryImport } from "@/lib/auth-gestionnaire";
import {
  ecrireComptesChoisis,
  fusionnerComptes,
  libelleIban,
  lireComptesChoisis,
  type CompteDigifactoryFiche,
  type UsageCompte,
} from "@/lib/fiches-import";

import type { Enregistrer } from "./ChampAuto";

type CompteAffiche = ReturnType<typeof fusionnerComptes>[number];

/** Les comptes du contact Digifactory. Chaque ligne se marque professionnelle
 * ou personnelle ; le choix reste sur la fiche. */
export function ComptesBancairesImport({
  ficheId,
  contact,
  valeur,
  modifiable,
  enregistrer,
}: {
  ficheId: string;
  contact: string;
  valeur: string;
  modifiable: boolean;
  enregistrer: Enregistrer;
}) {
  const [live, setLive] = useState<{ contact: string; comptes: CompteDigifactoryFiche[] | null } | null>(null);
  const [usages, setUsages] = useState<Record<string, UsageCompte>>({});
  const [enCours, setEnCours] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    if (!contact) return;
    let actif = true;
    comptesDigifactoryImport(ficheId, contact)
      .then((vue) => actif && setLive({ contact, comptes: vue.lu ? vue.comptes : null }))
      .catch(() => actif && setLive({ contact, comptes: null }));
    return () => {
      actif = false;
    };
  }, [ficheId, contact]);

  const reponse = live?.contact === contact ? live.comptes : contact ? undefined : null;
  const enLecture = Boolean(contact) && reponse === undefined;
  const lignes = fusionnerComptes(reponse ?? null, lireComptesChoisis(valeur)).map((compte) => ({
    ...compte,
    usage: usages[compte.id] ?? compte.usage,
  }));

  async function choisir(compte: CompteAffiche, usage: UsageCompte) {
    if (compte.usage === usage) return;
    const avant = usages;
    const suivants = lignes.map((ligne) => (ligne.id === compte.id ? { ...ligne, usage } : ligne));
    setUsages({ ...usages, [compte.id]: usage });
    setEnCours(compte.id);
    setErreur(null);
    try {
      await enregistrer({ comptes_bancaires: ecrireComptesChoisis(suivants) });
    } catch (exception) {
      setUsages(avant);
      setErreur(exception instanceof Error ? exception.message : "Erreur inattendue.");
    } finally {
      setEnCours(null);
    }
  }

  return (
    <section className="space-y-3" aria-labelledby="titre-comptes-import">
      <div>
        <h3 id="titre-comptes-import" className="text-sm font-medium text-ink">
          Comptes bancaires
        </h3>
        <p className="mt-1 text-sm text-subtle">
          Pro pour un compte de l&apos;activité, Perso pour un compte personnel.
        </p>
      </div>
      {contact && reponse === undefined && (
        <p className="flex items-center gap-2 text-sm text-subtle">
          <LoaderCircle className="size-4 animate-spin" aria-hidden /> Lecture des comptes…
        </p>
      )}
      {contact && reponse === null && (
        <p className="text-sm text-subtle">Digifactory n&apos;a pas donné les comptes.</p>
      )}
      {!contact && lignes.length === 0 && (
        <p className="text-sm text-subtle">Reliez le contact Digifactory pour voir ses comptes.</p>
      )}
      {contact && reponse !== undefined && reponse !== null && lignes.length === 0 && (
        <p className="text-sm text-subtle">Aucun compte remonté pour ce contact.</p>
      )}
      {lignes.length > 0 && (
        <ul className="divide-y divide-hairline border-y border-border">
          {lignes.map((compte) => (
            <LigneCompte
              key={compte.id}
              compte={compte}
              modifiable={modifiable && !enLecture}
              enCours={enCours !== null}
              onChoisir={(usage) => void choisir(compte, usage)}
            />
          ))}
        </ul>
      )}
      {erreur && <p role="alert" className="text-sm text-danger">{erreur}</p>}
    </section>
  );
}

function LigneCompte({
  compte,
  modifiable,
  enCours,
  onChoisir,
}: {
  compte: CompteAffiche;
  modifiable: boolean;
  enCours: boolean;
  onChoisir: (usage: UsageCompte) => void;
}) {
  const titre = [compte.banque, compte.nom].filter(Boolean).join(" · ") || "Compte";
  const iban = libelleIban(compte.iban, compte.fin);
  const signal =
    compte.usage === "" && compte.professionnel === true
      ? "La banque le signale comme professionnel."
      : compte.usage === "" && compte.professionnel === false
        ? "La banque le signale comme personnel."
        : "";
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 py-3">
      <div className="min-w-0">
        <p className="text-sm font-medium text-ink">{titre}</p>
        {(iban || signal) && (
          <p className="mt-0.5 text-xs text-muted">
            {iban && <span className="font-mono tracking-wide">{iban}</span>}
            {iban && signal && " · "}
            {signal}
          </p>
        )}
      </div>
      <div role="group" aria-label={`Usage de ${titre}`} className="inline-flex rounded-md bg-surface-soft p-0.5">
        <Choix usage="pro" choisi={compte.usage === "pro"} desactive={!modifiable || enCours} onChoisir={onChoisir}>
          Pro
        </Choix>
        <Choix usage="perso" choisi={compte.usage === "perso"} desactive={!modifiable || enCours} onChoisir={onChoisir}>
          Perso
        </Choix>
      </div>
    </li>
  );
}

function Choix({
  usage,
  choisi,
  desactive,
  onChoisir,
  children,
}: {
  usage: UsageCompte;
  choisi: boolean;
  desactive: boolean;
  onChoisir: (usage: UsageCompte) => void;
  children: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={choisi}
      disabled={desactive}
      onClick={() => onChoisir(usage)}
      className={`h-7 rounded-[5px] px-3 text-[13px] font-semibold transition-colors disabled:opacity-50 ${
        choisi ? "bg-canvas text-ink" : "text-subtle hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}
