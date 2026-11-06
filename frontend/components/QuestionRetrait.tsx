"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { libelleCategorie } from "@/lib/langage-chauffeur";
import {
  CATEGORIES_ACTIVITE_ESPECES,
  REPONSE_NE_SAIT_PLUS,
  REPONSE_PERSONNELLE,
  suiteDeLaReponse,
} from "@/lib/retrait-especes";

/** Retrait au distributeur (AXE-844) : « À quoi a servi cet argent ? »,
 * trois réponses. Une dépense pour l'activité demande ensuite sa catégorie
 * et son ticket ; « je ne sais plus » passe la main au comptable. */
export function QuestionRetrait({
  enCours = false,
  erreur = null,
  onReponse,
}: {
  enCours?: boolean;
  erreur?: string | null;
  onReponse: (categorie: string, libelle: string) => void;
}) {
  const [activite, setActivite] = useState(false);
  const [suite, setSuite] = useState<string | null>(null);

  function repondre(categorie: string, libelle: string) {
    if (enCours) return;
    setSuite(suiteDeLaReponse(categorie));
    onReponse(categorie, libelle);
  }

  return (
    <div className="rounded-md border border-warning/40 bg-pending-subtle p-3">
      <p className="mb-2 text-sm font-medium text-ink">
        {activite ? "Pour quelle dépense ?" : "À quoi a servi cet argent ?"}
      </p>
      {!activite ? (
        <div className="flex flex-col gap-2">
          <Button type="button" variant="secondary" className="h-11 w-full" disabled={enCours} onClick={() => setActivite(true)}>
            Une dépense pour mon activité
          </Button>
          <Button
            type="button"
            variant="secondary"
            className="h-11 w-full"
            disabled={enCours}
            onClick={() => repondre(REPONSE_PERSONNELLE, "dépense personnelle")}
          >
            Pour moi (personnel)
          </Button>
          <Button
            type="button"
            variant="secondary"
            className="h-11 w-full"
            disabled={enCours}
            onClick={() => repondre(REPONSE_NE_SAIT_PLUS, "à préciser par le comptable")}
          >
            Je ne sais plus
          </Button>
        </div>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {CATEGORIES_ACTIVITE_ESPECES.map((categorie) => (
            <Button
              key={categorie}
              type="button"
              variant="secondary"
              disabled={enCours}
              className="h-auto min-h-11 px-3 py-2"
              onClick={() => repondre(categorie, libelleCategorie(categorie))}
            >
              {libelleCategorie(categorie)}
            </Button>
          ))}
          <Button type="button" variant="ghost" disabled={enCours} className="min-h-11" onClick={() => setActivite(false)}>
            Retour
          </Button>
        </div>
      )}
      {suite && <p className="mt-2 text-sm text-ink">{suite}</p>}
      {erreur && <p className="mt-1 text-xs text-danger">{erreur}</p>}
    </div>
  );
}
