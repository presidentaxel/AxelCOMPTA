"use client";

import { useCallback, useId, useState } from "react";

import { Badge } from "@/components/Badge";
import { BoutonLien } from "@/components/BoutonLien";
import { Montant } from "@/components/Montant";
import { Squelette } from "@/components/Squelette";
import { Button } from "@/components/ui/button";
import { ZoneDeTexte } from "@/components/ZoneDeTexte";
import { lireHistoriqueAlerte } from "@/lib/auth-gestionnaire";
import {
  LIBELLE_ETAT,
  metaAlerte,
  motifValide,
  phraseEvenement,
  varianteEtat,
} from "@/lib/anomalies";
import type { AlerteAnomalie, EvenementAnomalie } from "@/lib/types";

/** Qualification d'une alerte (doc 05 §6.3). Le libellé vient du serveur.
 *
 * Carte d'anomalie (DESIGN.md › `anomaly-card`) : fond canvas, filet
 * `danger-border`, barre rouge de 3 px à gauche, aucune ombre. Les liens
 * d'action sont orange `signal` et soulignés ; le rouge reste sur la barre et
 * sur le montant, jamais sur une action. */
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
    <article className="rounded-lg border border-danger-border border-l-[3px] border-l-danger bg-canvas p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink">{alerte.libelle_ui}</p>
          <p className="mt-1 text-sm text-body">{alerte.detail}</p>
        </div>
        <Montant centimes={alerte.montant_centimes} className="shrink-0 text-lg font-semibold" />
      </div>
      <p className="mt-3 truncate text-sm text-ink">{alerte.libelle_mouvement}</p>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-subtle">
        <span>{metaAlerte(alerte)}</span>
        <Badge variant={varianteEtat(alerte.etat)}>{LIBELLE_ETAT[alerte.etat]}</Badge>
      </div>
      {alerte.etat === "ouverte" && (
        <BoutonLien
          className="mt-3"
          disabled={envoi || lecture}
          onClick={() => onDecider("en_instruction", "")}
        >
          Prendre en instruction<span aria-hidden="true">&nbsp;→</span>
        </BoutonLien>
      )}
      {alerte.etat === "en_instruction" && (
        <Qualification alerteId={alerte.id} envoi={envoi || lecture} onDecider={onDecider} />
      )}
      {alerte.etat !== "ouverte" && <Historique dossierId={dossierId} alerteId={alerte.id} />}
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
    // AXE-800 : chaque qualification porte le motif de l'expert.
    const motif = motifValide(commentaire);
    if (motif === null) {
      setManque(true);
      return;
    }
    setManque(false);
    onDecider(decision, motif);
  }
  return (
    <form
      className="mt-4 flex flex-col gap-2 border-t border-hairline pt-4"
      onSubmit={(evenement) => {
        evenement.preventDefault();
        decider("justifiee");
      }}
    >
      <label className="text-sm font-medium text-ink" htmlFor={champ}>
        Motif (obligatoire)
      </label>
      <ZoneDeTexte
        id={champ}
        name="commentaire"
        rows={3}
        value={commentaire}
        aria-invalid={manque || undefined}
        aria-describedby={manque ? `${champ}-manque` : undefined}
        onChange={(evenement) => setCommentaire(evenement.target.value)}
      />
      {manque && (
        <p id={`${champ}-manque`} className="text-sm text-danger">
          Indiquez le motif de votre décision.
        </p>
      )}
      {/* Une seule action principale : « Justifier » est aussi ce que valide la
          touche Entrée du formulaire. Les deux autres issues restent au filet. */}
      <div className="mt-1 flex flex-wrap gap-2">
        <Button type="submit" disabled={envoi}>
          Justifier
        </Button>
        <Button type="button" variant="secondary" disabled={envoi} onClick={() => decider("usage_personnel")}>
          Confirmer un usage personnel
        </Button>
        <Button type="button" variant="secondary" disabled={envoi} onClick={() => decider("faux_positif")}>
          Marquer comme faux positif
        </Button>
      </div>
    </form>
  );
}

/** Chaque changement d'état, qui l'a fait et quand (AXE-814). Relu à
 * chaque ouverture : une qualification faite entre-temps y figure. */
function Historique({ dossierId, alerteId }: { dossierId: string; alerteId: string }) {
  const liste = useId();
  const [evenements, setEvenements] = useState<EvenementAnomalie[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [ouvert, setOuvert] = useState(false);

  const lire = useCallback(() => {
    setErreur(null);
    lireHistoriqueAlerte(dossierId, alerteId)
      .then(setEvenements)
      .catch(() => setErreur("L'historique n'a pas pu être lu."));
  }, [dossierId, alerteId]);

  function basculer() {
    if (ouvert) {
      setOuvert(false);
      return;
    }
    setOuvert(true);
    lire();
  }

  return (
    <div className="mt-3">
      <BoutonLien aria-expanded={ouvert} aria-controls={liste} onClick={basculer}>
        {ouvert ? "Masquer l'historique" : "Historique"}
      </BoutonLien>
      <div id={liste}>
        {ouvert && erreur && (
          <p className="text-sm text-ink">
            {erreur}{" "}
            <BoutonLien className="min-h-0" onClick={lire}>
              Réessayer
            </BoutonLien>
          </p>
        )}
        {ouvert && !erreur && evenements === null && <Squelette className="mt-1 h-4 w-2/3" />}
        {ouvert && evenements && (
          <ol className="mt-1 space-y-1 text-sm text-subtle">
            {evenements.map((evenement) => (
              <li key={`${evenement.le}-${evenement.etat}`}>{phraseEvenement(evenement)}</li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
