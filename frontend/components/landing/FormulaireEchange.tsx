"use client";

import Link from "next/link";
import { useRef, useState, type FormEvent, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  SAISIE_VIDE,
  envoyerLaDemande,
  premiereErreur,
  type ChampEchange,
  type ErreurSaisie,
  type Profil,
  type SaisieEchange,
} from "@/lib/demande-echange";
import { ECHANGE } from "@/lib/landing-contenu";

const BASE_API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Etat = "saisie" | "envoi" | "envoyee";

const PROFILS: { valeur: Profil; libelle: string }[] = [
  { valeur: "cabinet", libelle: "Un cabinet" },
  { valeur: "centrale", libelle: "Une centrale" },
];

function Champ({
  id,
  libelle,
  erreur,
  facultatif = false,
  children,
}: {
  id: string;
  libelle: string;
  erreur: string | null;
  facultatif?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-ink">
        {libelle} {facultatif && <span className="font-normal text-muted">(facultatif)</span>}
      </label>
      {children}
      {erreur && (
        <p id={`${id}-erreur`} role="alert" className="text-[13px] text-danger">
          {erreur}
        </p>
      )}
    </div>
  );
}

/** La demande d'échange (AXE-949). Le contrôle côté navigateur évite un
 * aller-retour ; le serveur reste la référence et ses phrases s'affichent
 * telles quelles, sous le champ qu'elles visent. Le champ « site web » est un
 * piège à robots : invisible, hors de l'ordre de tabulation, jamais rempli
 * par une personne. Une demande envoyée remplace le formulaire par une
 * confirmation, pour qu'un second clic ne parte pas. */
export function FormulaireEchange() {
  const [saisie, setSaisie] = useState<SaisieEchange>(SAISIE_VIDE);
  const [erreur, setErreur] = useState<ErreurSaisie | null>(null);
  const [panne, setPanne] = useState<string | null>(null);
  const [etat, setEtat] = useState<Etat>("saisie");
  const champs = useRef<Partial<Record<ChampEchange, HTMLElement | null>>>({});

  function modifier(champ: keyof SaisieEchange, valeur: string) {
    setSaisie((avant) => ({ ...avant, [champ]: valeur }));
    if (erreur?.champ === champ) setErreur(null);
  }

  function montrer(nouvelle: ErreurSaisie) {
    setErreur(nouvelle);
    champs.current[nouvelle.champ]?.focus();
  }

  async function envoyer(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();
    setPanne(null);
    const invalide = premiereErreur(saisie);
    if (invalide) return montrer(invalide);
    setEtat("envoi");
    const resultat = await envoyerLaDemande(saisie, BASE_API);
    if (resultat.statut === "envoyee") return setEtat("envoyee");
    setEtat("saisie");
    if (resultat.statut === "refusee" && resultat.champ) {
      return montrer({ champ: resultat.champ, message: resultat.message });
    }
    setPanne(resultat.message);
  }

  if (etat === "envoyee") {
    return (
      <div role="status" className="rounded-lg border border-success-border bg-success-subtle p-6">
        <p className="text-lg font-semibold text-ink">{ECHANGE.succes}</p>
      </div>
    );
  }

  const messageDe = (champ: ChampEchange) => (erreur?.champ === champ ? erreur.message : null);
  const decrit = (champ: ChampEchange) => (erreur?.champ === champ ? `${champ}-erreur` : undefined);

  return (
    <form noValidate onSubmit={envoyer} className="relative flex min-w-0 flex-col gap-4">
      <div className="flex flex-wrap gap-4">
        <div className="min-w-0 flex-[1_1_200px]">
          <Champ id="nom" libelle="Nom" erreur={messageDe("nom")}>
            <Input
              id="nom"
              uiSize="lg"
              autoComplete="name"
              value={saisie.nom}
              aria-invalid={erreur?.champ === "nom"}
              aria-describedby={decrit("nom")}
              onChange={(e) => modifier("nom", e.target.value)}
              ref={(el) => {
                champs.current.nom = el;
              }}
            />
          </Champ>
        </div>
        <div className="min-w-0 flex-[1_1_200px]">
          <Champ id="email" libelle="E-mail professionnel" erreur={messageDe("email")}>
            <Input
              id="email"
              type="email"
              uiSize="lg"
              autoComplete="email"
              value={saisie.email}
              aria-invalid={erreur?.champ === "email"}
              aria-describedby={decrit("email")}
              onChange={(e) => modifier("email", e.target.value)}
              ref={(el) => {
                champs.current.email = el;
              }}
            />
          </Champ>
        </div>
      </div>
      <Champ id="organisation" libelle="Organisation" erreur={messageDe("organisation")}>
        <Input
          id="organisation"
          uiSize="lg"
          autoComplete="organization"
          value={saisie.organisation}
          aria-invalid={erreur?.champ === "organisation"}
          aria-describedby={decrit("organisation")}
          onChange={(e) => modifier("organisation", e.target.value)}
          ref={(el) => {
            champs.current.organisation = el;
          }}
        />
      </Champ>
      <fieldset className="m-0 flex min-w-0 flex-col gap-1.5 border-0 p-0">
        <legend className="mb-1.5 p-0 text-sm font-medium text-ink">Vous êtes</legend>
        <div className="flex flex-wrap gap-3">
          {PROFILS.map(({ valeur, libelle }, rang) => (
            <label
              key={valeur}
              htmlFor={`profil-${valeur}`}
              className="flex min-h-11 min-w-0 flex-[1_1_140px] cursor-pointer items-center gap-2.5 rounded-md border border-border-strong bg-canvas px-3.5 text-sm font-medium text-ink has-[:checked]:border-ink has-[:checked]:bg-primary-subtle has-[:focus-visible]:shadow-focus"
            >
              <input
                id={`profil-${valeur}`}
                type="radio"
                name="profil"
                value={valeur}
                checked={saisie.profil === valeur}
                aria-describedby={decrit("profil")}
                className="m-0 accent-primary"
                onChange={() => modifier("profil", valeur)}
                ref={
                  rang === 0
                    ? (el) => {
                        champs.current.profil = el;
                      }
                    : undefined
                }
              />
              {libelle}
            </label>
          ))}
        </div>
        {messageDe("profil") && (
          <p id="profil-erreur" role="alert" className="text-[13px] text-danger">
            {messageDe("profil")}
          </p>
        )}
      </fieldset>
      <Champ id="message" libelle="Message" erreur={messageDe("message")} facultatif>
        <textarea
          id="message"
          rows={3}
          value={saisie.message}
          aria-invalid={erreur?.champ === "message"}
          aria-describedby={decrit("message")}
          onChange={(e) => modifier("message", e.target.value)}
          ref={(el) => {
            champs.current.message = el;
          }}
          className="w-full min-w-0 resize-y rounded-md border border-border-strong bg-canvas px-3.5 py-2.5 text-base text-ink outline-none transition-colors duration-100 focus-visible:border-border-focus focus-visible:shadow-focus aria-invalid:border-danger"
        />
      </Champ>
      <div aria-hidden="true" className="absolute -left-[9999px] h-0 w-0 overflow-hidden">
        <label>
          Site web (laissez vide)
          <input
            type="text"
            name="site_web"
            tabIndex={-1}
            autoComplete="off"
            value={saisie.siteWeb}
            onChange={(e) => modifier("siteWeb", e.target.value)}
          />
        </label>
      </div>
      {panne && (
        <p role="alert" className="rounded-md border border-danger-border bg-danger-subtle px-3 py-2 text-sm text-ink">
          {panne}
        </p>
      )}
      <Button type="submit" size="lg" disabled={etat === "envoi"}>
        {etat === "envoi" ? ECHANGE.envoi : ECHANGE.action}
      </Button>
      <p className="text-xs leading-normal text-muted">
        {ECHANGE.mentionAvant}{" "}
        <Link
          href="/legal/confidentialite"
          className="font-semibold text-signal underline underline-offset-[3px]"
        >
          {ECHANGE.mentionLien}
        </Link>
      </p>
    </form>
  );
}
