"use client";

import { useRef, useState } from "react";

import { Badge } from "@/components/Badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import {
  deposerDocumentImport,
  retirerDocumentImport,
  telechargerDocumentImport,
} from "@/lib/auth-gestionnaire";
import { taille, type DocumentImport, type FicheImport } from "@/lib/fiches-import";

const SANS_EXERCICE = "aucun";

/** AXE-941 : les exercices à reprendre et leurs pièces (reprise comptable). */
export function ExercicesImport({ fiche }: { fiche: FicheImport }) {
  if (fiche.exercices.length === 0) {
    return (
      <p className="text-sm text-subtle">
        Indiquez la date de création et la date de clôture (catégorie Entreprise) : les exercices à reprendre
        et leurs pièces se calculent avec.
      </p>
    );
  }
  return (
    <ul className="space-y-3">
      {fiche.exercices.map((e) => (
        <li key={e.annee} className="rounded-md border border-border p-3">
          <p className="text-sm font-medium text-ink">
            Exercice {e.annee}{" "}
            <span className="font-normal text-subtle">
              du {new Date(e.debut).toLocaleDateString("fr-FR")} au {new Date(e.fin).toLocaleDateString("fr-FR")}
            </span>
          </p>
          {e.etat === "en_cours" ? (
            <p className="mt-1 text-sm text-subtle">En cours : la banque et Rollee le rempliront.</p>
          ) : (
            <ul className="mt-2 flex flex-wrap gap-2">
              {e.pieces.map((p) => (
                <li key={p.categorie}>
                  <Badge variant={p.recue ? "validated" : p.attendue ? "pending" : "missing"}>
                    {p.libelle} · {p.recue ? "reçu" : p.attendue ? "attendu" : "si disponible"}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ul>
  );
}

/** Déposer un document, et la liste de ceux déjà déposés. */
export function DocumentsImport({
  fiche,
  modifiable,
  categories,
  onFiche,
}: {
  fiche: FicheImport;
  modifiable: boolean;
  categories: string[];
  onFiche: (fiche: FicheImport) => void;
}) {
  const siens = fiche.documents.filter((d) => categories.includes(d.categorie));
  return (
    <div className="space-y-4">
      {modifiable && <DepotDocument fiche={fiche} categories={categories} onFiche={onFiche} />}
      {siens.length === 0 ? (
        <p className="text-sm text-subtle">Aucun document déposé.</p>
      ) : (
        <ul className="divide-y divide-border rounded-md border border-border">
          {siens.map((d) => (
            <LigneDocument key={d.id} fiche={fiche} document={d} modifiable={modifiable} onFiche={onFiche} />
          ))}
        </ul>
      )}
    </div>
  );
}

function DepotDocument({
  fiche,
  categories,
  onFiche,
}: {
  fiche: FicheImport;
  categories: string[];
  onFiche: (fiche: FicheImport) => void;
}) {
  const options = fiche.categories_documents.filter((c) => categories.includes(c.cle));
  const annees = fiche.exercices.filter((e) => e.etat === "clos").map((e) => String(e.annee));
  const [categorie, setCategorie] = useState(options[0]?.cle ?? "autre");
  const [exercice, setExercice] = useState(annees.at(-1) ?? SANS_EXERCICE);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const entree = useRef<HTMLInputElement>(null);

  async function deposer(fichiers: FileList | null) {
    const fichier = fichiers?.[0];
    if (!fichier) return;
    setEnvoi(true);
    setErreur(null);
    try {
      const annee = exercice === SANS_EXERCICE ? null : Number(exercice);
      onFiche(await deposerDocumentImport(fiche.id, fichier, categorie, annee));
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Erreur inattendue.");
    } finally {
      setEnvoi(false);
      if (entree.current) entree.current.value = "";
    }
  }

  return (
    <div className="flex flex-wrap items-end gap-3">
      <Select
        aria-label="Type de document"
        value={categorie}
        onValueChange={setCategorie}
        options={options.map((c) => ({ value: c.cle, label: c.libelle }))}
        className="min-w-48"
      />
      {annees.length > 0 && (
        <Select
          aria-label="Exercice"
          value={exercice}
          onValueChange={setExercice}
          options={[
            ...annees.map((a) => ({ value: a, label: `Exercice ${a}` })),
            { value: SANS_EXERCICE, label: "Sans exercice" },
          ]}
          className="min-w-36"
        />
      )}
      <input
        ref={entree}
        type="file"
        className="sr-only"
        aria-label="Fichier"
        accept=".pdf,.csv,.txt,.xml,.xls,.xlsx,.ods,.jpg,.jpeg,.png,.zip"
        onChange={(e) => deposer(e.target.files)}
      />
      <Button type="button" variant="secondary" disabled={envoi} onClick={() => entree.current?.click()}>
        {envoi ? "Envoi…" : "Déposer un fichier"}
      </Button>
      {erreur && <p role="alert" className="w-full text-sm text-danger">{erreur}</p>}
    </div>
  );
}

function LigneDocument({
  fiche,
  document,
  modifiable,
  onFiche,
}: {
  fiche: FicheImport;
  document: DocumentImport;
  modifiable: boolean;
  onFiche: (fiche: FicheImport) => void;
}) {
  async function ouvrir() {
    const blob = await telechargerDocumentImport(fiche.id, document.id);
    const lien = window.document.createElement("a");
    lien.href = URL.createObjectURL(blob);
    lien.download = document.nom_fichier;
    lien.click();
    URL.revokeObjectURL(lien.href);
  }

  return (
    <li className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm">
      <span>
        <span className="font-medium text-ink">{document.libelle}</span>
        {document.exercice && <span className="text-subtle"> {document.exercice}</span>}
        <span className="ml-2 text-subtle">
          {document.nom_fichier} · {taille(document.taille)} · {document.depose_par}
        </span>
      </span>
      <span className="flex gap-2">
        <Button size="sm" variant="ghost" onClick={ouvrir}>
          Télécharger
        </Button>
        {modifiable && (
          <Button
            size="sm"
            variant="ghost"
            onClick={async () => {
              if (window.confirm(`Retirer ${document.nom_fichier} ?`)) {
                onFiche(await retirerDocumentImport(fiche.id, document.id));
              }
            }}
          >
            Retirer
          </Button>
        )}
      </span>
    </li>
  );
}
