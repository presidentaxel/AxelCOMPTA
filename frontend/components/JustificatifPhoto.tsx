"use client";

import { useRef, useState } from "react";

import { ApiError } from "@/lib/api";
import { joindreJustificatifChauffeur } from "@/lib/auth-chauffeur";
import type { TransactionVue } from "@/lib/types";

/** doc 17 §9 Semaine 3, doc 19 §5.7 : « photo de justificatif au fil de
 * l'eau ». Pas d'attribut `capture` : sur ordinateur il n'ouvre que la
 * caméra, et sans caméra on ne peut pas choisir un fichier. `accept="image/*"`
 * laisse le téléphone proposer l'appareil photo ou la pellicule. Le contenu
 * n'est jamais lu côté serveur (pas d'OCR, doc 17 §8) — seule la présence
 * compte ici. */
export function JustificatifPhoto({
  dossierId,
  ecritureId,
  aJustificatif,
  onJointe,
}: {
  dossierId: string;
  ecritureId: string;
  aJustificatif: boolean;
  onJointe: (transaction: TransactionVue) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  async function joindre(fichier: File) {
    setEnCours(true);
    setErreur(null);
    try {
      const transaction = await joindreJustificatifChauffeur(dossierId, ecritureId, fichier);
      onJointe(transaction);
    } catch (exception) {
      setErreur(exception instanceof ApiError ? exception.message : "Échec de l'envoi de la photo.");
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(evenement) => {
          const fichier = evenement.target.files?.[0];
          if (fichier) void joindre(fichier);
          evenement.target.value = ""; // permet de reprendre une photo si l'envoi échoue
        }}
      />
      <button
        type="button"
        disabled={enCours}
        onClick={() => inputRef.current?.click()}
        className={`inline-flex min-h-11 items-center py-1 text-sm font-medium outline-none focus-visible:shadow-focus-detache ${aJustificatif ? "text-validated" : "text-primary"} disabled:opacity-50`}
      >
        {aJustificatif ? "Photo jointe" : enCours ? "Envoi…" : "Ajouter une photo"}
      </button>
      {erreur && <p className="mt-1 text-xs text-danger">{erreur}</p>}
    </div>
  );
}
