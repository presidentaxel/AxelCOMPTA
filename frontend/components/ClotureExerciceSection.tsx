"use client";

// Louis, 2026-09-26 : la clôture appartient au chauffeur, légalement
// responsable de sa comptabilité. L'API a tout préparé ; il relit ce que la
// clôture va faire, accepte l'attestation et valide. Personne d'autre ne
// peut le faire à sa place, et sans lui rien ne se passe.
import { useCallback, useEffect, useState } from "react";

import { ProvisionsCloture } from "@/components/ProvisionsCloture";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  ErreurAuthChauffeur,
  fetchAvecAuthChauffeur,
  validerClotureChauffeur,
} from "@/lib/auth-chauffeur";
import { formatDate } from "@/lib/format";
import type { ClotureExerciceVue } from "@/lib/types";

export function ClotureExerciceSection({
  dossierId,
  onClos,
}: {
  dossierId: string;
  onClos: () => void;
}) {
  const [apercu, setApercu] = useState<ClotureExerciceVue | null>(null);
  const [accepte, setAccepte] = useState(false);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(() => {
    fetchAvecAuthChauffeur<ClotureExerciceVue>(`/dossiers/${dossierId}/cloture-exercice`)
      .then(setApercu)
      .catch(() => setApercu(null));
  }, [dossierId]);

  useEffect(() => {
    charger();
  }, [charger]);

  if (apercu === null) {
    return null;
  }
  if (!apercu.possible) {
    // Exercice en cours : rien à clore, la section reste discrète.
    return apercu.raison && !apercu.raison.includes("pas terminé") ? (
      <section className="mt-8">
        <h2 className="text-sm font-medium text-ink">Clôture de l&apos;exercice</h2>
        <p className="mt-2 text-sm text-subtle">{apercu.raison}</p>
      </section>
    ) : null;
  }

  async function valider(attestation: string) {
    setEnCours(true);
    setErreur(null);
    try {
      await validerClotureChauffeur(dossierId, attestation);
      onClos();
    } catch (exception) {
      setErreur(
        exception instanceof ErreurAuthChauffeur || exception instanceof ApiError
          ? exception.message
          : "Échec de la clôture.",
      );
    } finally {
      setEnCours(false);
    }
  }

  return (
    <section className="mt-8">
      <h2 className="text-sm font-medium text-ink">Clôture de l&apos;exercice</h2>
      <p className="mt-2 text-sm text-subtle">
        Exercice du {formatDate(apercu.exercice_debut)} au {formatDate(apercu.exercice_fin)}.
        C&apos;est à vous de le clore : rien n&apos;est fait sans votre validation.
      </p>
      <ProvisionsCloture dossierId={dossierId} onChange={charger} />
      <ul className="mt-3 space-y-1 text-sm text-ink">
        {apercu.ecritures.map((libelle) => (
          <li key={libelle}>{libelle}</li>
        ))}
        {apercu.nouvel_exercice_debut && (
          <li>Ouverture du nouvel exercice le {formatDate(apercu.nouvel_exercice_debut)}</li>
        )}
        {apercu.changements.map((changement) => (
          <li key={changement}>{changement}</li>
        ))}
      </ul>
      {apercu.attestation && (
        <>
          <label className="mt-4 flex gap-3 rounded-md border border-border bg-canvas p-3 text-sm text-ink">
            <input
              type="checkbox"
              className="mt-1"
              checked={accepte}
              onChange={(evenement) => setAccepte(evenement.target.checked)}
            />
            <span>{apercu.attestation}</span>
          </label>
          <Button
            className="mt-3"
            disabled={!accepte || enCours}
            onClick={() => apercu.attestation && valider(apercu.attestation)}
          >
            {enCours ? "Clôture…" : "Valider la clôture"}
          </Button>
        </>
      )}
      {erreur && <p className="mt-2 text-sm text-danger">{erreur}</p>}
    </section>
  );
}
