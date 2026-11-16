"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Squelette } from "@/components/Squelette";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { creerTag, lireTags, listerDossiers, reglerExclusion } from "@/lib/auth-gestionnaire";
import { basculerExclusion, compterParTag, libelleTag, phraseEntreprises } from "@/lib/tags";
import type { DossierAgregat, ReglageTags } from "@/lib/types";
import { useDroitGestionnaire } from "@/lib/use-droit";

function messageErreur(exception: unknown): string {
  return exception instanceof Error ? exception.message : "L'opération a échoué.";
}

/** AXE-957 : les tags du portefeuille et les traitements dont chacun sort
 * ses entreprises. Sorti d'Entreprises : c'est un réglage, rarement touché. */
export default function PageTags() {
  const droit = useDroitGestionnaire();
  const [reglage, setReglage] = useState<ReglageTags | null>(null);
  const [dossiers, setDossiers] = useState<DossierAgregat[]>([]);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(() => {
    setErreur(null);
    lireTags()
      .then(setReglage)
      .catch((exception) => setErreur(messageErreur(exception)));
    listerDossiers()
      .then(setDossiers)
      .catch(() => setDossiers([]));
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    charger();
  }, [charger]);

  const nombres = useMemo(() => compterParTag(dossiers), [dossiers]);

  function appliquer(promesse: Promise<ReglageTags>) {
    setErreur(null);
    promesse.then(setReglage).catch((exception) => setErreur(messageErreur(exception)));
  }

  return (
    <div className="max-w-3xl">
      <Link href="/portefeuille" className="text-sm text-subtle hover:text-ink">
        ← Entreprises
      </Link>
      <h1 className="mt-2 text-[22px] font-bold tracking-tight text-ink">Tags</h1>
      <p className="mt-1 text-sm text-subtle">
        Un tag regroupe des entreprises. Il peut les sortir de certains traitements : rien n&apos;est
        supprimé, et retirer l&apos;exclusion les fait revenir. Les tags se posent depuis la fiche
        d&apos;une entreprise, ou en cochant plusieurs entreprises dans la liste.
      </p>

      {erreur && <p className="mt-4 text-sm text-danger">{erreur}</p>}

      {!reglage && !erreur && (
        <div className="mt-6 space-y-3" aria-hidden>
          <Squelette className="h-32 w-full" />
          <Squelette className="h-32 w-full" />
        </div>
      )}

      {reglage && (
        <ul className="mt-6 space-y-3">
          {reglage.tags.map((tag) => (
            <li key={tag.nom}>
              <CarteTag
                nom={tag.nom}
                description={tag.description}
                nombre={nombres[tag.nom] ?? 0}
                reglage={reglage}
                ecriture={droit.ecriture}
                onBasculer={(traitement, exclus) =>
                  appliquer(reglerExclusion(traitement, basculerExclusion(exclus, tag.nom)))
                }
              />
            </li>
          ))}
        </ul>
      )}

      {reglage && droit.ecriture && <NouveauTag onCreer={(nom) => appliquer(creerTag(nom))} />}
    </div>
  );
}

function CarteTag({
  nom,
  description,
  nombre,
  reglage,
  ecriture,
  onBasculer,
}: {
  nom: string;
  description: string;
  nombre: number;
  reglage: ReglageTags;
  ecriture: boolean;
  onBasculer: (traitement: string, exclus: string[]) => void;
}) {
  const traitements = Object.entries(reglage.traitements);
  return (
    <Card>
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="text-base font-semibold text-ink">{libelleTag(nom)}</h2>
        <Link
          href={`/portefeuille?tag=${encodeURIComponent(nom)}`}
          className="shrink-0 text-sm text-signal hover:underline"
        >
          {phraseEntreprises(nombre)}
        </Link>
      </div>
      {description && <p className="mt-1 text-sm text-subtle">{description}</p>}
      <fieldset className="mt-4">
        <legend className="text-sm font-medium text-ink">Sortir ces entreprises de</legend>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {traitements.map(([traitement, libelle]) => {
            const exclus = reglage.exclusions[traitement] ?? [];
            return (
              <label
                key={traitement}
                className="flex items-center gap-2.5 rounded-md border border-hairline px-3 py-2 text-sm text-ink has-[:checked]:border-primary has-[:checked]:bg-surface-soft"
              >
                <input
                  type="checkbox"
                  checked={exclus.includes(nom)}
                  disabled={!ecriture}
                  onChange={() => onBasculer(traitement, exclus)}
                />
                {libelle}
              </label>
            );
          })}
        </div>
      </fieldset>
    </Card>
  );
}

function NouveauTag({ onCreer }: { onCreer: (nom: string) => void }) {
  const [nom, setNom] = useState("");
  return (
    <form
      className="mt-6 flex flex-wrap items-center gap-2"
      onSubmit={(evenement) => {
        evenement.preventDefault();
        if (!nom.trim()) return;
        onCreer(nom.trim());
        setNom("");
      }}
    >
      <Input
        value={nom}
        onChange={(evenement) => setNom(evenement.target.value)}
        placeholder="Nom du nouveau tag"
        aria-label="Nom du nouveau tag"
        className="w-64"
      />
      <Button type="submit" variant="secondary" size="sm">
        Créer le tag
      </Button>
    </form>
  );
}
