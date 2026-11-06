"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { lireHistoriqueAlerte } from "@/lib/auth-gestionnaire";
import { formatDate, formatMontant } from "@/lib/format";
import type { AlerteAnomalie, EvenementAnomalie } from "@/lib/types";

const SUITE: Record<AlerteAnomalie["etat"], string> = {
  ouverte: "Ouverte",
  en_instruction: "En instruction",
  justifiee: "Justifiée",
  usage_personnel: "Usage personnel confirmé",
  faux_positif: "Faux positif",
};

/** Qualification d'une alerte (doc 05 §6.3). Le libellé vient du serveur. */
export function InstructionAlerte({
  dossierId,
  alerte,
  envoi,
  lecture = false,
  onDecider,
}: {
  dossierId: string;
  alerte: AlerteAnomalie;
  envoi: boolean;
  lecture?: boolean;
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
      <p className="mt-2 text-xs text-subtle">
        {formatDate(alerte.date)} · {SUITE[alerte.etat]}
      </p>
      {alerte.etat === "ouverte" && (
        <Button
          type="button"
          className="mt-3"
          disabled={envoi || lecture}
          onClick={() => onDecider("en_instruction", "")}
        >
          Prendre en instruction
        </Button>
      )}
      {alerte.etat === "en_instruction" && (
        <Qualification alerteId={alerte.id} envoi={envoi || lecture} onDecider={onDecider} />
      )}
      {alerte.etat !== "ouverte" && (
        <Historique dossierId={dossierId} alerteId={alerte.id} />
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
  const [commentaire, setCommentaire] = useState("");
  const [manque, setManque] = useState(false);
  function decider(decision: "justifiee" | "usage_personnel" | "faux_positif") {
    if (decision === "justifiee" && !commentaire.trim()) {
      setManque(true);
      return;
    }
    setManque(false);
    onDecider(decision, commentaire.trim());
  }
  return (
    <form
      className="mt-3 flex flex-col gap-2"
      onSubmit={(evenement) => {
        evenement.preventDefault();
        decider("justifiee");
      }}
    >
      <label className="text-sm text-ink" htmlFor={champ}>
        Commentaire
      </label>
      <textarea
        id={champ}
        name="commentaire"
        rows={2}
        value={commentaire}
        onChange={(evenement) => setCommentaire(evenement.target.value)}
        className="rounded-md border border-hairline px-3 py-2 text-sm text-ink"
      />
      {manque && <p className="text-sm text-danger">Un commentaire est nécessaire pour justifier.</p>}
      <Button type="submit" disabled={envoi}>
        Justifier
      </Button>
      <Button type="button" variant="secondary" disabled={envoi} onClick={() => decider("usage_personnel")}>
        Confirmer un usage personnel
      </Button>
      <Button type="button" variant="secondary" disabled={envoi} onClick={() => decider("faux_positif")}>
        Marquer comme faux positif
      </Button>
    </form>
  );
}

/** Chaque changement d'état, qui l'a fait et quand (AXE-814). Relu à
 * chaque ouverture : une qualification faite entre-temps y figure. */
function Historique({ dossierId, alerteId }: { dossierId: string; alerteId: string }) {
  const [evenements, setEvenements] = useState<EvenementAnomalie[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [ouvert, setOuvert] = useState(false);
  function basculer() {
    if (ouvert) {
      setOuvert(false);
      return;
    }
    setOuvert(true);
    setErreur(null);
    lireHistoriqueAlerte(dossierId, alerteId)
      .then(setEvenements)
      .catch(() => setErreur("Impossible de lire l'historique."));
  }
  return (
    <div className="mt-2">
      <button
        type="button"
        className="text-xs font-medium text-primary hover:underline"
        aria-expanded={ouvert}
        onClick={basculer}
      >
        {ouvert ? "Masquer l'historique" : "Historique"}
      </button>
      {ouvert && erreur && <p className="mt-1 text-xs text-danger">{erreur}</p>}
      {ouvert && evenements && (
        <ol className="mt-1 space-y-1 text-xs text-subtle">
          {evenements.map((evenement) => (
            <li key={`${evenement.le}-${evenement.etat}`}>
              {formatDate(evenement.le)} · {SUITE[evenement.etat as AlerteAnomalie["etat"]] ?? evenement.etat}{" "}
              · {evenement.acteur}
              {evenement.commentaire ? ` · « ${evenement.commentaire} »` : ""}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
