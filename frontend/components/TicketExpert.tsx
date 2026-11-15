"use client";

import { useState } from "react";

import { joindreTicketExpert, lireTicketExpert } from "@/lib/auth-gestionnaire";

/** Le ticket de la ligne : le voir, en ajouter un, ou constater qu'il manque. */
export function TicketExpert({
  dossierId,
  ecritureId,
  present,
  onAjoute,
}: {
  dossierId: string;
  ecritureId: string;
  present: boolean;
  onAjoute: () => void;
}) {
  const [apercu, setApercu] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  async function voir() {
    setErreur(null);
    try {
      const photo = await lireTicketExpert(dossierId, ecritureId);
      if (apercu) URL.revokeObjectURL(apercu);
      setApercu(URL.createObjectURL(photo));
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Le ticket n'a pas pu être lu.");
    }
  }

  async function ajouter(fichier: File | undefined) {
    if (!fichier) return;
    setErreur(null);
    try {
      await joindreTicketExpert(dossierId, ecritureId, fichier);
      onAjoute();
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Le ticket n'a pas pu être ajouté.");
    }
  }

  return (
    <div className="mt-2 flex flex-wrap items-center gap-3">
      {present ? (
        <button type="button" onClick={() => void voir()} className="text-sm font-medium text-signal hover:underline">
          Voir le ticket
        </button>
      ) : (
        <span className="text-sm text-subtle">Aucun ticket</span>
      )}
      <label className="text-sm font-medium text-signal hover:underline">
        Ajouter un ticket
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
          className="sr-only"
          onChange={(evenement) => void ajouter(evenement.target.files?.[0])}
        />
      </label>
      {erreur && <span className="text-sm text-danger">{erreur}</span>}
      {apercu && (
        // Le ticket est une photo prise par le chauffeur : next/image n'a pas cette URL locale.
        // eslint-disable-next-line @next/next/no-img-element
        <img src={apercu} alt="Ticket de la ligne" className="mt-1 max-h-48 rounded-md border border-hairline" />
      )}
    </div>
  );
}
