"use client";

// Louis, 2026-09-26 : la clôture appartient au chauffeur, légalement
// responsable de sa comptabilité. L'API a tout préparé ; il relit ce que la
// clôture va faire, accepte l'attestation et valide. Personne d'autre ne
// peut le faire à sa place, et sans lui rien ne se passe.
import { useCallback, useEffect, useState } from "react";

import { EtatErreur } from "@/components/EtatChargement";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  ErreurAuthChauffeur,
  fetchAvecAuthChauffeur,
  validerClotureChauffeur,
} from "@/lib/auth-chauffeur";
import { formatDate } from "@/lib/format";
import { messageVisible } from "@/lib/messages";
import type { ClotureExerciceVue } from "@/lib/types";
import { Squelette } from "@/components/Squelette";

export function ClotureExerciceSection({
  dossierId,
  relecture = 0,
  onClos,
}: {
  dossierId: string;
  relecture?: number;
  onClos: () => void;
}) {
  const [apercu, setApercu] = useState<ClotureExerciceVue | null>(null);
  const [echec, setEchec] = useState<string | null>(null);
  const [accepte, setAccepte] = useState(false);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [succes, setSucces] = useState<string | null>(null);

  const charger = useCallback(() => {
    let annule = false;
    fetchAvecAuthChauffeur<ClotureExerciceVue>(`/dossiers/${dossierId}/cloture-exercice`)
      .then((vue) => {
        if (annule) return;
        setApercu(vue);
        setEchec(null);
      })
      .catch((exception: unknown) => {
        if (annule) return;
        setApercu(null);
        setEchec(messageVisible(exception, "Impossible de charger la clôture."));
      });
    return () => {
      annule = true;
    };
  }, [dossierId]);

  useEffect(() => charger(), [charger, relecture]);

  if (echec) {
    return (
      <section className="mt-8">
        <h2 className="text-sm font-medium text-ink">Clôture de l&apos;exercice</h2>
        <EtatErreur
          message={echec}
          onReessayer={() => {
            setEchec(null);
            setApercu(null);
            charger();
          }}
        />
      </section>
    );
  }
  if (apercu === null) {
    return <Squelette className="mt-8 h-24 w-full" />;
  }
  if (!apercu.possible) {
    return (
      <section className="mt-8">
        <h2 className="text-sm font-medium text-ink">Clôture de l&apos;exercice</h2>
        <p className="mt-2 text-sm text-subtle">
          {succes ?? apercu.raison ?? "La clôture n'est pas disponible pour le moment."}
        </p>
      </section>
    );
  }

  async function valider(attestation: string) {
    setEnCours(true);
    setErreur(null);
    try {
      const vue = await validerClotureChauffeur(dossierId, attestation);
      setApercu(vue);
      setSucces(vue.raison ?? "L'exercice est clos.");
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
      {succes && <p className="mt-3 text-sm text-ink">{succes}</p>}
      {erreur && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {erreur}
        </p>
      )}
    </section>
  );
}
