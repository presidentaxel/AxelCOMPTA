"use client";

import { Check, CircleDashed, Download, FileText, LoaderCircle, Trash2, UploadCloud, X } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import {
  deposerDocumentImport,
  retirerDocumentImport,
  telechargerDocumentImport,
} from "@/lib/auth-gestionnaire";
import {
  devinerCategorie,
  devinerExercice,
  taille,
  type DocumentImport,
  type FicheImport,
} from "@/lib/fiches-import";

const SANS_EXERCICE = "aucun";
const FORMATS = ".pdf,.csv,.txt,.xml,.xls,.xlsx,.ods,.jpg,.jpeg,.png,.zip";

type EnAttente = {
  cle: string;
  fichier: File;
  categorie: string;
  exercice: string;
  etat: "pret" | "envoi" | "fait" | "erreur";
  erreur?: string;
};

/** AXE-946 : les pièces attendues par exercice (reprise comptable). */
export function PiecesAttendues({ fiche }: { fiche: FicheImport }) {
  if (fiche.exercices.length === 0) {
    return (
      <p className="rounded-md bg-canvas-app p-3 text-sm text-subtle">
        Indiquez la date de création et la date de clôture (Entreprise) : les exercices à reprendre et leurs
        pièces se calculent avec.
      </p>
    );
  }
  return (
    <ol className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {fiche.exercices.map((e) => (
        <li key={e.annee} className="rounded-lg border border-border p-4">
          <p className="flex items-baseline justify-between gap-2">
            <span className="font-medium text-ink">Exercice {e.annee}</span>
            <span className="text-xs text-muted">
              {new Date(e.debut).toLocaleDateString("fr-FR")} → {new Date(e.fin).toLocaleDateString("fr-FR")}
            </span>
          </p>
          {e.etat === "en_cours" ? (
            <p className="mt-2 text-sm text-subtle">En cours : la banque et Rollee le rempliront.</p>
          ) : (
            <ul className="mt-2 space-y-1.5">
              {e.pieces.map((p) => (
                <li key={p.categorie} className="flex items-center gap-2 text-sm">
                  {p.recue ? (
                    <Check className="size-4 text-success" aria-hidden />
                  ) : (
                    <CircleDashed className={`size-4 ${p.attendue ? "text-warning" : "text-faint"}`} aria-hidden />
                  )}
                  <span className={p.recue || p.attendue ? "text-ink" : "text-subtle"}>{p.libelle}</span>
                  <span className="ml-auto text-xs text-muted">
                    {p.recue ? "reçu" : p.attendue ? "attendu" : "si disponible"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ol>
  );
}

/** Glisser-déposer plusieurs fichiers, un type et un exercice par fichier,
 * puis la liste des documents déjà déposés. */
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
      {modifiable && <ZoneDepot fiche={fiche} categories={categories} onFiche={onFiche} />}
      {siens.length > 0 && (
        <ul className="divide-y divide-border rounded-md border border-border">
          {siens.map((d) => (
            <LigneDocument key={d.id} fiche={fiche} document={d} modifiable={modifiable} onFiche={onFiche} />
          ))}
        </ul>
      )}
    </div>
  );
}

function ZoneDepot({
  fiche,
  categories,
  onFiche,
}: {
  fiche: FicheImport;
  categories: string[];
  onFiche: (fiche: FicheImport) => void;
}) {
  const [file, setFile] = useState<EnAttente[]>([]);
  const [survol, setSurvol] = useState(false);
  const [envoi, setEnvoi] = useState(false);
  const entree = useRef<HTMLInputElement>(null);
  const options = fiche.categories_documents.filter((c) => categories.includes(c.cle));
  const annees = fiche.exercices.filter((e) => e.etat === "clos").map((e) => e.annee);

  function ajouter(fichiers: FileList | null) {
    const nouveaux = Array.from(fichiers ?? []).map((fichier, i): EnAttente => {
      const exercice = devinerExercice(fichier.name, annees) ?? annees.at(-1) ?? null;
      return {
        cle: `${Date.now()}-${i}-${fichier.name}`,
        fichier,
        categorie: devinerCategorie(fichier.name, categories, categories[0] ?? "autre"),
        exercice: exercice === null ? SANS_EXERCICE : String(exercice),
        etat: "pret",
      };
    });
    setFile((avant) => [...avant.filter((f) => f.etat !== "fait"), ...nouveaux]);
  }

  function changer(cle: string, modif: Partial<EnAttente>) {
    setFile((avant) => avant.map((f) => (f.cle === cle ? { ...f, ...modif } : f)));
  }

  async function toutEnvoyer() {
    setEnvoi(true);
    for (const element of file.filter((f) => f.etat === "pret" || f.etat === "erreur")) {
      changer(element.cle, { etat: "envoi", erreur: undefined });
      try {
        const annee = element.exercice === SANS_EXERCICE ? null : Number(element.exercice);
        onFiche(await deposerDocumentImport(fiche.id, element.fichier, element.categorie, annee));
        changer(element.cle, { etat: "fait" });
      } catch (exception) {
        changer(element.cle, {
          etat: "erreur",
          erreur: exception instanceof Error ? exception.message : "Erreur inattendue.",
        });
      }
    }
    setEnvoi(false);
  }

  const aEnvoyer = file.filter((f) => f.etat === "pret" || f.etat === "erreur").length;
  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={() => entree.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setSurvol(true);
        }}
        onDragLeave={() => setSurvol(false)}
        onDrop={(e) => {
          e.preventDefault();
          setSurvol(false);
          ajouter(e.dataTransfer.files);
        }}
        className={`flex w-full flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-8 text-center transition-colors ${
          survol ? "border-ink bg-surface-soft" : "border-border-strong bg-canvas-app hover:bg-surface-soft"
        }`}
      >
        <UploadCloud className="size-7 text-subtle" aria-hidden />
        <span className="text-sm font-medium text-ink">Glissez vos fichiers ici, ou cliquez pour les choisir</span>
        <span className="text-xs text-muted">PDF, FEC (TXT), CSV, Excel, images ou ZIP · 20 Mo par fichier</span>
      </button>
      <input
        ref={entree}
        type="file"
        multiple
        className="sr-only"
        aria-label="Fichiers"
        accept={FORMATS}
        onChange={(e) => {
          ajouter(e.target.files);
          e.target.value = "";
        }}
      />
      {file.length > 0 && (
        <ul className="space-y-2">
          {file.map((f) => (
            <LigneEnAttente
              key={f.cle}
              element={f}
              options={options.map((c) => ({ value: c.cle, label: c.libelle }))}
              annees={annees}
              onChanger={(modif) => changer(f.cle, modif)}
              onRetirer={() => setFile((avant) => avant.filter((x) => x.cle !== f.cle))}
            />
          ))}
        </ul>
      )}
      {aEnvoyer > 0 && (
        <Button onClick={toutEnvoyer} disabled={envoi}>
          {envoi ? "Envoi…" : `Envoyer ${aEnvoyer} fichier${aEnvoyer > 1 ? "s" : ""}`}
        </Button>
      )}
    </div>
  );
}

function LigneEnAttente({
  element,
  options,
  annees,
  onChanger,
  onRetirer,
}: {
  element: EnAttente;
  options: { value: string; label: string }[];
  annees: number[];
  onChanger: (modif: Partial<EnAttente>) => void;
  onRetirer: () => void;
}) {
  const bloque = element.etat === "envoi" || element.etat === "fait";
  return (
    <li className="rounded-md border border-border p-3">
      <div className="flex flex-wrap items-center gap-3">
        <FileText className="size-4 shrink-0 text-subtle" aria-hidden />
        <span className="min-w-0 flex-1 truncate text-sm text-ink" title={element.fichier.name}>
          {element.fichier.name}
          <span className="ml-2 text-xs text-muted">{taille(element.fichier.size)}</span>
        </span>
        <Select
          aria-label={`Type de ${element.fichier.name}`}
          value={element.categorie}
          disabled={bloque}
          onValueChange={(categorie) => onChanger({ categorie })}
          options={options}
          className="min-w-44"
        />
        {annees.length > 0 && (
          <Select
            aria-label={`Exercice de ${element.fichier.name}`}
            value={element.exercice}
            disabled={bloque}
            onValueChange={(exercice) => onChanger({ exercice })}
            options={[
              ...annees.map((a) => ({ value: String(a), label: `Exercice ${a}` })),
              { value: SANS_EXERCICE, label: "Sans exercice" },
            ]}
            className="min-w-36"
          />
        )}
        <EtatEnvoi element={element} onRetirer={onRetirer} />
      </div>
      {element.erreur && <p role="alert" className="mt-2 text-xs text-danger">{element.erreur}</p>}
    </li>
  );
}

function EtatEnvoi({ element, onRetirer }: { element: EnAttente; onRetirer: () => void }) {
  if (element.etat === "envoi") return <LoaderCircle className="size-4 animate-spin text-muted" aria-label="Envoi" />;
  if (element.etat === "fait") return <Check className="size-4 text-success" aria-label="Envoyé" />;
  return (
    <Button size="sm" variant="ghost" aria-label={`Retirer ${element.fichier.name}`} onClick={onRetirer}>
      <X className="size-4" aria-hidden />
    </Button>
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
    <li className="flex flex-wrap items-center gap-3 px-3 py-2.5 text-sm">
      <FileText className="size-4 shrink-0 text-subtle" aria-hidden />
      <span className="min-w-0 flex-1">
        <span className="font-medium text-ink">
          {document.libelle}
          {document.exercice && ` ${document.exercice}`}
        </span>
        <span className="ml-2 truncate text-subtle">
          {document.nom_fichier} · {taille(document.taille)} · {document.depose_par}
        </span>
      </span>
      <Button size="sm" variant="ghost" onClick={ouvrir} aria-label={`Télécharger ${document.nom_fichier}`}>
        <Download className="size-4" aria-hidden />
      </Button>
      {modifiable && (
        <Button
          size="sm"
          variant="ghost"
          aria-label={`Retirer ${document.nom_fichier}`}
          onClick={async () => {
            if (window.confirm(`Retirer ${document.nom_fichier} ?`)) {
              onFiche(await retirerDocumentImport(fiche.id, document.id));
            }
          }}
        >
          <Trash2 className="size-4" aria-hidden />
        </Button>
      )}
    </li>
  );
}
