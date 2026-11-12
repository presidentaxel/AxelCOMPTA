"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { creerTag, poserTag, reglerExclusion } from "@/lib/auth-gestionnaire";
import { basculerExclusion, libelleTag } from "@/lib/tags";
import type { ReglageTags } from "@/lib/types";

/** Tags d'une entreprise, en pastilles discrètes (AXE-829). */
export function PastillesTags({ tags }: { tags: string[] }) {
  if (tags.length === 0) return null;
  return (
    <span className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <span
          key={tag}
          className="rounded-full border border-border px-2 py-0.5 text-xs text-subtle"
        >
          {libelleTag(tag)}
        </span>
      ))}
    </span>
  );
}

function messageErreur(exception: unknown): string {
  return exception instanceof Error ? exception.message : "L'opération a échoué.";
}

/** Fiche entreprise : chaque tag du portefeuille se pose ou se retire d'un clic. */
export function TagsDuDossier({
  dossierId,
  tags,
  reglage,
  ecriture,
  onModifie,
}: {
  dossierId: string;
  tags: string[];
  reglage: ReglageTags | null;
  ecriture: boolean;
  onModifie: () => void;
}) {
  const [erreur, setErreur] = useState<string | null>(null);
  if (!reglage) return null;
  return (
    <div className="mt-8">
      <p className="text-sm font-medium text-ink">Tags</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {reglage.tags.map((tag) => {
          const pose = tags.includes(tag.nom);
          return (
            <button
              key={tag.nom}
              type="button"
              title={tag.description}
              aria-pressed={pose}
              disabled={!ecriture}
              onClick={() => {
                setErreur(null);
                poserTag(tag.nom, [dossierId], !pose)
                  .then(onModifie)
                  .catch((exception) => setErreur(messageErreur(exception)));
              }}
              className={`rounded-full border px-3 py-1 text-xs disabled:opacity-60 ${
                pose ? "border-primary bg-primary text-white" : "border-border text-ink hover:bg-surface-soft"
              }`}
            >
              {libelleTag(tag.nom)}
            </button>
          );
        })}
      </div>
      {erreur && <p className="mt-2 text-sm text-danger">{erreur}</p>}
    </div>
  );
}

/** Barre d'action quand des entreprises sont cochées dans la liste. */
export function PoseEnLot({
  coches,
  reglage,
  onFait,
}: {
  coches: string[];
  reglage: ReglageTags | null;
  onFait: () => void;
}) {
  const [tag, setTag] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  if (coches.length === 0 || !reglage) return null;
  const choisi = tag || reglage.tags[0]?.nom || "";
  function appliquer(pose: boolean) {
    setErreur(null);
    poserTag(choisi, coches, pose)
      .then(onFait)
      .catch((exception) => setErreur(messageErreur(exception)));
  }
  return (
    <div className="mt-4 flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface-soft px-3 py-2 text-sm">
      <span className="text-ink">
        {coches.length === 1 ? "1 entreprise cochée" : `${coches.length} entreprises cochées`}
      </span>
      <Select
        aria-label="Tag à poser"
        value={choisi}
        onValueChange={setTag}
        options={reglage.tags
          .filter((option) => option.nom !== "")
          .map((option) => ({ value: option.nom, label: libelleTag(option.nom) }))}
        className="w-48"
      />
      {/* Secondaires : le seul bouton principal de l'écran Entreprises est « Synchroniser ». */}
      <Button type="button" variant="secondary" size="sm" onClick={() => appliquer(true)}>
        Poser
      </Button>
      <Button type="button" variant="ghost" size="sm" onClick={() => appliquer(false)}>
        Retirer
      </Button>
      {erreur && <span className="text-danger">{erreur}</span>}
    </div>
  );
}

/** Quels tags sortent une entreprise de quel traitement. Ses données restent :
 * décocher la fait revenir. Réservé aux rôles qui écrivent. */
export function ReglageExclusions({
  reglage,
  ecriture,
  onModifie,
}: {
  reglage: ReglageTags;
  ecriture: boolean;
  onModifie: (reglage: ReglageTags) => void;
}) {
  const [nouveau, setNouveau] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  function appliquer(promesse: Promise<ReglageTags>) {
    setErreur(null);
    promesse.then(onModifie).catch((exception) => setErreur(messageErreur(exception)));
  }
  return (
    <details className="mt-6 rounded-lg border border-border bg-canvas p-4">
      <summary className="cursor-pointer text-sm font-semibold text-ink">Tags et exclusions</summary>
      <p className="mt-2 text-sm text-subtle">
        Une entreprise portant un tag coché sort du traitement. Rien n&apos;est supprimé.
      </p>
      <div className="mt-3 overflow-x-auto">
        <table className="text-sm">
          <thead>
            <tr>
              <th className="pr-4 text-left font-medium text-subtle">Traitement</th>
              {reglage.tags.map((tag) => (
                <th key={tag.nom} className="px-2 font-medium text-subtle" title={tag.description}>
                  {libelleTag(tag.nom)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.entries(reglage.traitements).map(([traitement, libelle]) => {
              const exclus = reglage.exclusions[traitement] ?? [];
              return (
                <tr key={traitement} className="border-t border-hairline">
                  <td className="py-1.5 pr-4 text-ink">{libelle}</td>
                  {reglage.tags.map((tag) => (
                    <td key={tag.nom} className="px-2 text-center">
                      <input
                        type="checkbox"
                        aria-label={`${libelleTag(tag.nom)} exclu de : ${libelle}`}
                        checked={exclus.includes(tag.nom)}
                        disabled={!ecriture}
                        onChange={() =>
                          appliquer(reglerExclusion(traitement, basculerExclusion(exclus, tag.nom)))
                        }
                      />
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {ecriture && (
        <form
          className="mt-4 flex items-center gap-2"
          onSubmit={(evenement) => {
            evenement.preventDefault();
            if (!nouveau.trim()) return;
            appliquer(creerTag(nouveau.trim()));
            setNouveau("");
          }}
        >
          <Input
            value={nouveau}
            onChange={(evenement) => setNouveau(evenement.target.value)}
            placeholder="Nouveau tag"
            aria-label="Nouveau tag"
          />
          <Button type="submit" variant="secondary" size="sm">
            Créer
          </Button>
        </form>
      )}
      {erreur && <p className="mt-2 text-sm text-danger">{erreur}</p>}
    </details>
  );
}
