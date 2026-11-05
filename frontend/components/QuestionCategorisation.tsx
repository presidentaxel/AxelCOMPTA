"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  RACCOURCIS_CATEGORIE,
  intituleProposition,
  libelleCategorie,
  questionSelonSigne,
} from "@/lib/langage-chauffeur";
import type { TransactionVue } from "@/lib/types";

const PERSONNELLE = "dépense personnelle";
const REMUNERATION = "ma rémunération";

/** doc 19 §5.6 : « petites questions de catégorisation ... présentée
 * simplement » — même mécanisme de revue que doc 17 §9 bloc C (désormais
 * exclusivement indiv, doc 19 §2.1) mais sans le vocabulaire comptable
 * ("471", "reclasser") : trois réponses fermées d'abord (personnelle, sa
 * rémunération, autre chose), un champ libre seulement pour « autre chose ».
 * L'enregistrement (et son annulation) est à la charge de l'écran. */
export function QuestionCategorisation({
  proposition,
  montantCts,
  origine = null,
  sansProposition = false,
  raccourci = false,
  corriger = false,
  enCours = false,
  erreur = null,
  onReponse,
}: {
  proposition: { code: string; libelle: string } | null;
  montantCts: number;
  /** D'où vient la proposition : choix passés du chauffeur, ou une règle. */
  origine?: TransactionVue["origine_proposition"];
  /** Vrai quand le libellé ne porte aucune catégorie. */
  sansProposition?: boolean;
  /** « O » confirme la proposition. Une seule question de l'écran le porte. */
  raccourci?: boolean;
  /** L'opération a déjà une catégorie : on la remplace. */
  corriger?: boolean;
  enCours?: boolean;
  erreur?: string | null;
  onReponse: (categorie: string, libelle: string) => void;
}) {
  const [autreCategorie, setAutreCategorie] = useState("");
  const [afficherAutre, setAfficherAutre] = useState(false);
  const parti = useRef(false);
  const pointeurFin = usePointeurFin();
  const montreTouche = raccourci && pointeurFin;

  useEffect(() => {
    if (erreur) parti.current = false;
  }, [erreur]);

  const repondre = useCallback(
    (categorie: string, libelle: string) => {
      if (parti.current || enCours || !categorie.trim()) return;
      parti.current = true;
      onReponse(categorie.trim(), libelle);
    },
    [enCours, onReponse],
  );

  useEffect(() => {
    if (!raccourci || !proposition || afficherAutre) return;
    const code = proposition.code;
    const libelle = proposition.libelle;
    function surTouche(evenement: KeyboardEvent) {
      if (evenement.repeat) return;
      if (evenement.key.toLowerCase() !== "o") return;
      if (evenement.metaKey || evenement.ctrlKey || evenement.altKey) return;
      const cible = evenement.target;
      if (cible instanceof HTMLElement && cible.closest("input, textarea, select")) return;
      evenement.preventDefault();
      repondre(code, libelle);
    }
    window.addEventListener("keydown", surTouche);
    return () => window.removeEventListener("keydown", surTouche);
  }, [afficherAutre, proposition, raccourci, repondre]);

  return (
    <div className="rounded-md border border-warning/40 bg-pending-subtle p-3">
      <p className="mb-2 text-sm font-medium text-ink">
        {corriger
          ? "Changer la catégorie ?"
          : proposition
            ? intituleProposition(proposition.libelle, origine)
            : questionSelonSigne(montantCts, sansProposition)}
      </p>
      {!afficherAutre ? (
        <div className="flex flex-col gap-2">
          {proposition && (
            <Button
              type="button"
              variant="secondary"
              className="h-auto min-h-11 w-full px-3 whitespace-normal!"
              disabled={enCours}
              aria-keyshortcuts={montreTouche ? "o" : undefined}
              onClick={() => repondre(proposition.code, proposition.libelle)}
            >
              Oui, c&apos;est ça
              {montreTouche && <Touche>O</Touche>}
            </Button>
          )}
          <Button
            type="button"
            variant="secondary"
            className="h-11 w-full"
            disabled={enCours}
            onClick={() => repondre("usage_personnel", PERSONNELLE)}
          >
            Personnelle
          </Button>
          {/* Louis, 2026-09-26 : le chauffeur se paie et catégorise sa paie
              lui-même ; le compte (641, 644, 108) dépend de sa forme. */}
          <Button
            type="button"
            variant="secondary"
            className="h-11 w-full"
            disabled={enCours}
            onClick={() => repondre("remuneration_dirigeant", REMUNERATION)}
          >
            Ma rémunération
          </Button>
          <Button
            type="button"
            variant="secondary"
            className="h-11 w-full"
            disabled={enCours}
            onClick={() => setAfficherAutre(true)}
          >
            Autre chose
          </Button>
        </div>
      ) : (
        <div>
          {/* Catégories dont le compte dépend du statut : l'API répond
              clairement si elle ne s'applique pas à ce dossier. */}
          <div className="mb-2 flex flex-wrap gap-1.5">
            {RACCOURCIS_CATEGORIE.map((categorie) => (
              <Button
                key={categorie}
                type="button"
                variant="secondary"
                disabled={enCours}
                className="h-auto min-h-11 max-w-full whitespace-normal! px-3 py-2"
                onClick={() => repondre(categorie, libelleCategorie(categorie))}
              >
                {libelleCategorie(categorie)}
              </Button>
            ))}
          </div>
          <form
            className="flex items-center gap-2"
            onSubmit={(evenement) => {
              evenement.preventDefault();
              repondre(autreCategorie, autreCategorie.trim());
            }}
          >
            <Input
              type="text"
              value={autreCategorie}
              onChange={(evenement) => setAutreCategorie(evenement.target.value)}
              placeholder="en quelques mots"
              autoFocus
              disabled={enCours}
              className="h-11 min-w-0 flex-1 text-base"
            />
            <Button
              type="submit"
              variant="secondary"
              disabled={enCours || !autreCategorie.trim()}
              className="h-11 shrink-0"
            >
              Envoyer
            </Button>
          </form>
        </div>
      )}
      {erreur && <p className="mt-1 text-xs text-danger">{erreur}</p>}
    </div>
  );
}

/** Le raccourci clavier ne s'affiche pas sur un écran tactile. */
function usePointeurFin(): boolean {
  const [fin, setFin] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(hover: hover) and (pointer: fine)");
    const maj = () => setFin(media.matches);
    maj();
    media.addEventListener("change", maj);
    return () => media.removeEventListener("change", maj);
  }, []);
  return fin;
}

function Touche({ children }: { children: string }) {
  return (
    <kbd className="rounded-xs border border-border-strong bg-canvas-app px-1.5 py-px text-xs font-medium text-subtle shadow-[0_1px_0_var(--color-border-strong)]">
      {children}
    </kbd>
  );
}

