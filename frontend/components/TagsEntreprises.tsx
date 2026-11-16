"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { poserTag } from "@/lib/auth-gestionnaire";
import { libelleTag } from "@/lib/tags";
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
    <div>
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
