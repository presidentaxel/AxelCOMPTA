"use client";

import { Button } from "@/components/ui/button";
import { formatMontant } from "@/lib/format";
import type { AlerteAnomalie } from "@/lib/types";

const SUITE: Record<AlerteAnomalie["etat"], string> = {
  ouverte: "Ouverte",
  en_instruction: "En instruction",
  justifiee: "Justifiée",
  usage_personnel: "Usage personnel confirmé",
  faux_positif: "Faux positif",
};

/** Qualification d'une alerte (doc 05 §6.3). Le libellé vient du serveur. */
export function InstructionAlerte({
  alerte,
  envoi,
  onDecider,
}: {
  alerte: AlerteAnomalie;
  envoi: boolean;
  onDecider: (decision: AlerteAnomalie["etat"], commentaire: string) => void;
}) {
  return (
    <article className="border-b border-hairline py-4">
      <p className="text-sm font-medium text-ink">{alerte.libelle_ui}</p>
      <p className="mt-1 text-sm text-subtle">{alerte.detail}</p>
      <p className="mt-2 flex items-baseline justify-between gap-3 text-sm">
        <span className="min-w-0 truncate text-ink">{alerte.libelle_mouvement}</span>
        <span className="shrink-0 tabular-nums text-amount-negative">
          {formatMontant(alerte.montant_centimes)}
        </span>
      </p>
      <p className="mt-2 text-xs text-subtle">{SUITE[alerte.etat]}</p>
      {alerte.etat === "ouverte" && (
        <Button
          type="button"
          className="mt-3"
          disabled={envoi}
          onClick={() => onDecider("en_instruction", "")}
        >
          Prendre en instruction
        </Button>
      )}
      {alerte.etat === "en_instruction" && (
        <Qualification alerteId={alerte.id} envoi={envoi} onDecider={onDecider} />
      )}
    </article>
  );
}

function Qualification({
  alerteId,
  envoi,
  onDecider,
}: {
  alerteId: string;
  envoi: boolean;
  onDecider: (decision: AlerteAnomalie["etat"], commentaire: string) => void;
}) {
  const champ = `commentaire-${alerteId}`;
  return (
    <form
      className="mt-3 flex flex-col gap-2"
      onSubmit={(evenement) => {
        evenement.preventDefault();
        const donnees = new FormData(evenement.currentTarget);
        onDecider("justifiee", String(donnees.get("commentaire") ?? ""));
      }}
    >
      <label className="text-sm text-ink" htmlFor={champ}>
        Commentaire
      </label>
      <textarea
        id={champ}
        name="commentaire"
        rows={2}
        className="rounded-md border border-hairline px-3 py-2 text-sm text-ink"
      />
      <Button type="submit" disabled={envoi}>
        Justifier
      </Button>
      <Button type="button" variant="secondary" disabled={envoi} onClick={() => onDecider("usage_personnel", "")}>
        Confirmer un usage personnel
      </Button>
      <Button type="button" variant="secondary" disabled={envoi} onClick={() => onDecider("faux_positif", "")}>
        Marquer comme faux positif
      </Button>
    </form>
  );
}
