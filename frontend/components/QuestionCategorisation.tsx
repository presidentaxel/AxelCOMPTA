"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { trancherTransactionChauffeur } from "@/lib/auth-chauffeur";
import type { TransactionVue } from "@/lib/types";

const RACCOURCIS = [
  ["dividendes", "Mes dividendes"],
  ["impots_dividendes", "Impôts sur mes dividendes"],
  ["cotisations_dirigeant", "Mes cotisations sociales"],
  ["prelevement_source_paie", "Impôt prélevé sur ma paie"],
  ["compte_courant_associe", "Apport ou remboursement d'associé"],
  ["virement_interne", "Virement entre mes comptes"],
  ["salaires_personnel", "Salaire d'un salarié"],
] as const;

/** doc 19 §5.6 : « petites questions de catégorisation ... présentée
 * simplement » — même mécanisme de revue que doc 17 §9 bloc C (désormais
 * exclusivement indiv, doc 19 §2.1) mais sans le vocabulaire comptable
 * ("471", "reclasser") : trois réponses fermées d'abord (personnelle, sa
 * rémunération, autre chose), un champ libre seulement pour « autre chose ». */
export function QuestionCategorisation({
  dossierId,
  ecritureId,
  proposition,
  origine = null,
  confiance = null,
  sansProposition = false,
  raccourci = false,
  onResolu,
}: {
  dossierId: string;
  ecritureId: string;
  proposition: { code: string; libelle: string } | null;
  /** D'où vient la proposition : choix passés du chauffeur, règle ou modèle. */
  origine?: TransactionVue["origine_proposition"];
  confiance?: number | null;
  /** Vrai quand le libellé ne porte aucune catégorie : le modèle n'a pas tourné. */
  sansProposition?: boolean;
  /** « O » confirme la proposition. Une seule question de l'écran le porte. */
  raccourci?: boolean;
  onResolu: (transaction: TransactionVue) => void;
}) {
  const [autreCategorie, setAutreCategorie] = useState("");
  const [afficherAutre, setAfficherAutre] = useState(false);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const enCoursRef = useRef(false);

  const repondre = useCallback(
    async (categorie: string) => {
      if (enCoursRef.current || !categorie.trim()) return;
      enCoursRef.current = true;
      setEnCours(true);
      setErreur(null);
      try {
        const transaction = await trancherTransactionChauffeur(
          dossierId,
          ecritureId,
          categorie.trim(),
        );
        onResolu(transaction);
      } catch (exception) {
        setErreur(exception instanceof ApiError ? exception.message : "Échec de l'envoi.");
      } finally {
        enCoursRef.current = false;
        setEnCours(false);
      }
    },
    [dossierId, ecritureId, onResolu],
  );

  useEffect(() => {
    if (!raccourci || !proposition || afficherAutre) return;
    const code = proposition.code;
    function surTouche(evenement: KeyboardEvent) {
      if (evenement.key.toLowerCase() !== "o") return;
      if (evenement.metaKey || evenement.ctrlKey || evenement.altKey) return;
      const cible = evenement.target;
      if (cible instanceof HTMLElement && cible.closest("input, textarea, select")) return;
      evenement.preventDefault();
      void repondre(code);
    }
    window.addEventListener("keydown", surTouche);
    return () => window.removeEventListener("keydown", surTouche);
  }, [afficherAutre, proposition, raccourci, repondre]);

  return (
    <div className="rounded-md border border-warning/40 bg-pending-subtle p-3">
      <p className="mb-2 text-sm font-medium text-ink">
        {proposition
          ? intitule(proposition.libelle, origine, confiance)
          : sansProposition
            ? "Pas de proposition automatique. À quoi correspond cette dépense ?"
            : "À quoi correspond cette dépense ?"}
      </p>
      {!afficherAutre ? (
        <div className="flex flex-col gap-2">
          {proposition && (
            <Button
              type="button"
              variant="secondary"
              className="h-auto min-h-11 w-full px-3 whitespace-normal!"
              disabled={enCours}
              aria-keyshortcuts={raccourci ? "o" : undefined}
              onClick={() => repondre(proposition.code)}
            >
              Oui, c&apos;est ça
              {raccourci && <Touche>O</Touche>}
            </Button>
          )}
          <Button
            type="button"
            variant="secondary"
            className="h-11 w-full"
            disabled={enCours}
            onClick={() => repondre("usage_personnel")}
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
            onClick={() => repondre("remuneration_dirigeant")}
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
            {RACCOURCIS.map(([categorie, libelle]) => (
              <Button
                key={categorie}
                type="button"
                variant="secondary"
                size="sm"
                disabled={enCours}
                className="max-w-full whitespace-normal!"
                onClick={() => repondre(categorie)}
              >
                {libelle}
              </Button>
            ))}
          </div>
          <form
            className="flex items-center gap-2"
            onSubmit={(evenement) => {
              evenement.preventDefault();
              void repondre(autreCategorie);
            }}
          >
            <Input
              type="text"
              value={autreCategorie}
              onChange={(evenement) => setAutreCategorie(evenement.target.value)}
              placeholder="à quoi correspond-elle ?"
              autoFocus
              disabled={enCours}
              className="h-7 min-w-0 flex-1 text-xs"
            />
            <Button
              type="submit"
              variant="secondary"
              size="sm"
              disabled={enCours || !autreCategorie.trim()}
              className="shrink-0"
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

/** Le chauffeur voit d'où vient la proposition : ce qu'il a déjà classé lui-même,
 * ou le modèle et sa confiance. */
function Touche({ children }: { children: string }) {
  return (
    <kbd className="rounded-xs border border-border-strong bg-canvas-app px-1.5 py-px text-[11px] font-medium text-subtle shadow-[0_1px_0_var(--color-border-strong)]">
      {children}
    </kbd>
  );
}

function intitule(
  libelle: string,
  origine: TransactionVue["origine_proposition"],
  confiance: number | null,
): string {
  if (origine === "appris") return `Comme une opération déjà classée : ${libelle}`;
  if (origine === "modele" && confiance !== null) {
    return `Proposition du modèle (${Math.round(confiance * 100)} %) : ${libelle}`;
  }
  return `Proposition : ${libelle}`;
}
