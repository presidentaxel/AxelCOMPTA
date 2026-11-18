"use client";

import { AlertTriangle, Check, Download, FileText, LoaderCircle, Plus, Trash2, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";

import { Badge } from "@/components/Badge";
import { Button } from "@/components/ui/button";
import {
  deposerDocumentImport,
  deposerDocumentsExercice,
  lireFicheImport,
  rangerDocumentImport,
  retirerDocumentImport,
  telechargerDocumentImport,
} from "@/lib/auth-gestionnaire";
import {
  ajouterAnnee,
  CATEGORIES_EXERCICE,
  deplacerDocument,
  documentsVisibles,
  lireAnnee,
  archiveDe,
  nomCourt,
  versions,
  phraseDepot,
  basculerRetard,
  libelleTraitement,
  parExercice,
  phraseExercice,
  retardPossible,
  taille,
  valeurChamp,
  type DocumentImport,
  type EmplacementImport,
  type ExerciceImport,
  type FicheImport,
} from "@/lib/fiches-import";

const FORMATS = ".pdf,.qif,.csv,.txt,.xml,.xls,.xlsx,.ods,.jpg,.jpeg,.png,.zip";
type Envoi = { cle: string; nom: string; erreur?: string };

/** AXE-947 : les emplacements d'une catégorie, un par document attendu.
 * En reprise, rangés par exercice. */
export function EmplacementsSection({
  fiche,
  section,
  modifiable,
  onFiche,
  enregistrer,
}: {
  fiche: FicheImport;
  section: string;
  modifiable: boolean;
  onFiche: (fiche: FicheImport) => void;
  enregistrer: (champs: Record<string, string>) => Promise<void>;
}) {
  const siens = fiche.emplacements.filter((e) => e.section === section);
  const essais = useRef(new Map<string, number>());
  const suites = useRef(new Map<string, Promise<void>>());
  const [erreurs, setErreurs] = useState<Record<string, string>>({});
  if (siens.length === 0) return null;
  const groupes = new Map(parExercice(siens));

  /** Le document change de carte tout de suite. Seul le dernier choix de ce
   * document est envoyé, puis remplace la fiche ; un échec la relit. */
  function ranger(document: DocumentImport, categorie: string) {
    const emplacement = `reprise:${categorie}:${document.exercice}`;
    if (emplacement === document.emplacement) return;
    const ticket = (essais.current.get(document.id) ?? 0) + 1;
    essais.current.set(document.id, ticket);
    setErreurs((courant) => ({ ...courant, [document.id]: "" }));
    const avant = fiche;
    onFiche(deplacerDocument(fiche, document.id, emplacement));
    const suite = (suites.current.get(document.id) ?? Promise.resolve()).then(async () => {
      if (essais.current.get(document.id) !== ticket) return;
      try {
        const suivante = await rangerDocumentImport(fiche.id, document.id, emplacement);
        if (essais.current.get(document.id) === ticket) onFiche(suivante);
      } catch (exception) {
        if (essais.current.get(document.id) !== ticket) return;
        const message = exception instanceof Error ? exception.message : "Erreur inattendue.";
        setErreurs((courant) => ({ ...courant, [document.id]: message }));
        try {
          onFiche(await lireFicheImport(fiche.id));
        } catch {
          onFiche(avant);
        }
      }
    });
    suites.current.set(
      document.id,
      suite.then(
        () => undefined,
        () => undefined,
      ),
    );
  }

  const grille = (liste: EmplacementImport[]) => (
    <div className="grid gap-3 md:grid-cols-2">
      {liste.map((e) => (
        <CarteEmplacement
          key={e.cle}
          fiche={fiche}
          emplacement={e}
          modifiable={modifiable}
          onFiche={onFiche}
          onRanger={ranger}
          erreurs={erreurs}
        />
      ))}
    </div>
  );
  if (section !== "reprise") return grille(siens);
  const exercices = [...fiche.exercices].sort((a, b) => b.annee - a.annee);
  return (
    <div className="space-y-6">
      {modifiable && <AjouterExercice fiche={fiche} enregistrer={enregistrer} />}
      {exercices.map((e) => (
        <div key={e.annee} className="space-y-3">
          <EnTeteExercice
            exercice={e}
            enRetard={valeurChamp(fiche, "en_retard")}
            modifiable={modifiable}
            enregistrer={enregistrer}
          />
          {modifiable && e.etat === "clos" && <DepotExercice fiche={fiche} annee={e.annee} onFiche={onFiche} />}
          {grille(groupes.get(e.annee) ?? [])}
        </div>
      ))}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-ink">Autres documents</h3>
        {grille(groupes.get(null) ?? [])}
      </div>
    </div>
  );
}

/** AXE-970 : reprendre un exercice plus ancien que ceux proposés, depuis 2000,
 * même avec des trous (2019 sans 2020). */
function AjouterExercice({
  fiche,
  enregistrer,
}: {
  fiche: FicheImport;
  enregistrer: (champs: Record<string, string>) => Promise<void>;
}) {
  const [annee, setAnnee] = useState("");
  const [erreur, setErreur] = useState("");
  const [envoi, setEnvoi] = useState(false);
  const connues = new Set(fiche.exercices.map((e) => e.annee));

  async function ajouter() {
    const lue = lireAnnee(annee, new Date());
    if (typeof lue === "string") return setErreur(lue);
    if (connues.has(lue)) return setErreur(`L'exercice ${lue} est déjà dans la liste.`);
    setEnvoi(true);
    setErreur("");
    try {
      await enregistrer({ exercices_ajoutes: ajouterAnnee(valeurChamp(fiche, "exercices_ajoutes"), lue) });
      setAnnee("");
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Erreur inattendue.");
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <form
      className="flex flex-wrap items-end gap-3 rounded-lg border border-border p-4"
      onSubmit={(e) => {
        e.preventDefault();
        void ajouter();
      }}
    >
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium text-ink">Importer un exercice d&apos;une autre année</span>
        <span className="text-xs text-subtle">
          L&apos;année de clôture, depuis 2000. Un exercice manquant entre deux n&apos;empêche rien.
        </span>
        <input
          inputMode="numeric"
          maxLength={4}
          placeholder="2019"
          value={annee}
          onChange={(e) => setAnnee(e.target.value)}
          className="h-11 w-28 rounded-md border border-border-strong bg-surface px-3 text-ink"
          aria-label="Année de clôture de l'exercice à ajouter"
        />
      </label>
      <Button type="submit" disabled={envoi || !annee}>
        {envoi ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : <Plus className="size-4" aria-hidden />}
        Ajouter l&apos;exercice
      </Button>
      {erreur && <p className="w-full text-sm text-danger">{erreur}</p>}
    </form>
  );
}

/** AXE-970 : tout le dossier d'un exercice déposé d'un coup (fichiers ou archive
 * zip) ; chaque fichier est rangé dans sa catégorie, et se reclasse ensuite. */
function DepotExercice({
  fiche,
  annee,
  onFiche,
}: {
  fiche: FicheImport;
  annee: number;
  onFiche: (fiche: FicheImport) => void;
}) {
  const [survol, setSurvol] = useState(false);
  const [etat, setEtat] = useState<{ envoi: boolean; message: string; erreur: boolean }>({
    envoi: false,
    message: "",
    erreur: false,
  });
  const entree = useRef<HTMLInputElement>(null);

  async function deposer(liste: FileList | null) {
    const fichiers = Array.from(liste ?? []);
    if (fichiers.length === 0) return;
    setEtat({ envoi: true, message: `Envoi de ${fichiers.length} fichier(s)…`, erreur: false });
    try {
      const apres = await deposerDocumentsExercice(fiche.id, annee, fichiers);
      onFiche(apres);
      setEtat({ envoi: false, message: phraseDepot(fichiers.length, apres.doublons_ecartes ?? []), erreur: false });
    } catch (exception) {
      const message = exception instanceof Error ? exception.message : "Erreur inattendue.";
      setEtat({ envoi: false, message, erreur: true });
    }
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setSurvol(true);
      }}
      onDragLeave={() => setSurvol(false)}
      onDrop={(e) => {
        e.preventDefault();
        setSurvol(false);
        void deposer(e.dataTransfer.files);
      }}
      className={`rounded-lg border border-dashed p-3 transition-colors ${
        survol ? "border-ink bg-surface-soft" : "border-border-strong"
      }`}
    >
      <button
        type="button"
        disabled={etat.envoi}
        onClick={() => entree.current?.click()}
        className="flex min-h-11 w-full items-center justify-center gap-2 text-sm text-subtle hover:text-ink"
      >
        {etat.envoi ? (
          <LoaderCircle className="size-4 animate-spin" aria-hidden />
        ) : (
          <UploadCloud className="size-4" aria-hidden />
        )}
        Déposer tout le dossier {annee} : classé automatiquement, archives zip dépliées
      </button>
      <input
        ref={entree}
        type="file"
        multiple
        className="sr-only"
        aria-label={`Déposer des fichiers de l'exercice ${annee}`}
        accept={FORMATS}
        onChange={(e) => {
          void deposer(e.target.files);
          e.target.value = "";
        }}
      />
      {etat.message && (
        <p className={`mt-1 text-center text-xs ${etat.erreur ? "text-danger" : "text-subtle"}`}>{etat.message}</p>
      )}
    </div>
  );
}

/** AXE-950 : l'exercice, son rôle pour la reprise et, une fois la date
 * limite passée, « Pas déposée (en retard) ». */
function EnTeteExercice({
  exercice,
  enRetard,
  modifiable,
  enregistrer,
}: {
  exercice: ExerciceImport;
  enRetard: string;
  modifiable: boolean;
  enregistrer: (champs: Record<string, string>) => Promise<void>;
}) {
  const [envoi, setEnvoi] = useState(false);
  const du = new Date(exercice.debut).toLocaleDateString("fr-FR");
  const au = new Date(exercice.fin).toLocaleDateString("fr-FR");
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-2">
      <div>
        <h3 className="text-sm font-semibold text-ink">
          Exercice {exercice.annee}{" "}
          <span className="font-normal text-subtle">
            du {du} au {au}
          </span>
        </h3>
        <p className="mt-0.5 text-xs text-subtle">{phraseExercice(exercice)}</p>
      </div>
      {modifiable && retardPossible(exercice) && (
        <Button
          size="sm"
          variant={exercice.en_retard ? "secondary" : "ghost"}
          aria-pressed={exercice.en_retard}
          disabled={envoi}
          onClick={async () => {
            setEnvoi(true);
            try {
              await enregistrer({ en_retard: basculerRetard(enRetard, exercice.annee) });
            } finally {
              setEnvoi(false);
            }
          }}
        >
          {envoi && <LoaderCircle className="size-3.5 animate-spin" aria-hidden />}
          {exercice.en_retard ? "Pas déposée (en retard)" : "Liasse pas déposée ?"}
        </Button>
      )}
    </div>
  );
}

function CarteEmplacement({
  fiche,
  emplacement,
  modifiable,
  onFiche,
  onRanger,
  erreurs,
}: {
  fiche: FicheImport;
  emplacement: EmplacementImport;
  modifiable: boolean;
  onFiche: (fiche: FicheImport) => void;
  onRanger: (document: DocumentImport, categorie: string) => void;
  erreurs: Record<string, string>;
}) {
  const [survol, setSurvol] = useState(false);
  const [envois, setEnvois] = useState<Envoi[]>([]);
  const [tout, setTout] = useState(false);
  const entree = useRef<HTMLInputElement>(null);
  const rempli = emplacement.documents.length > 0;
  const enDouble = versions(emplacement.cle.split(":")[1] ?? "", emplacement.documents);
  const { visibles, caches } = documentsVisibles(emplacement.documents, tout);

  async function deposer(fichiers: FileList | null) {
    const liste = Array.from(fichiers ?? []);
    const nouveaux = liste.map((f, i) => ({ cle: `${Date.now()}-${i}`, nom: f.name }));
    setEnvois((avant) => [...avant, ...nouveaux]); // visibles tout de suite
    for (const [i, fichier] of liste.entries()) {
      try {
        onFiche(await deposerDocumentImport(fiche.id, fichier, emplacement.cle));
        setEnvois((avant) => avant.filter((e) => e.cle !== nouveaux[i].cle));
      } catch (exception) {
        const erreur = exception instanceof Error ? exception.message : "Erreur inattendue.";
        setEnvois((avant) => avant.map((e) => (e.cle === nouveaux[i].cle ? { ...e, erreur } : e)));
      }
    }
  }

  return (
    <div
      onDragOver={(e) => {
        if (!modifiable) return;
        e.preventDefault();
        setSurvol(true);
      }}
      onDragLeave={() => setSurvol(false)}
      onDrop={(e) => {
        e.preventDefault();
        setSurvol(false);
        if (modifiable) void deposer(e.dataTransfer.files);
      }}
      className={`flex flex-col gap-3 rounded-lg border p-4 transition-colors ${
        survol ? "border-ink bg-surface-soft" : rempli ? "border-border" : "border-dashed border-border-strong"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium text-ink">{emplacement.libelle}</p>
          <p className="mt-0.5 text-xs text-subtle">{emplacement.explication}</p>
          {enDouble > 1 && (
            <p className="mt-1 text-xs text-warning">
              {enDouble} versions de ce document : gardez la bonne, retirez les autres.
            </p>
          )}
        </div>
        <Badge variant={rempli ? "validated" : emplacement.attendu ? "pending" : "missing"}>
          {rempli ? "Reçu" : emplacement.attendu ? "Attendu" : "Facultatif"}
        </Badge>
      </div>
      {(emplacement.documents.length > 0 || envois.length > 0) && (
        <ul className="space-y-2">
          {visibles.map((d) => (
            <LigneDocument
              key={d.id}
              fiche={fiche}
              document={d}
              modifiable={modifiable}
              onFiche={onFiche}
              onRanger={onRanger}
              erreur={erreurs[d.id] ?? ""}
            />
          ))}
          {caches > 0 && (
            <li>
              <Button size="sm" variant="ghost" onClick={() => setTout(true)}>
                Voir les {caches} autres
              </Button>
            </li>
          )}
          {envois.map((e) => (
            <li key={e.cle} className="flex items-center gap-2 text-sm">
              {e.erreur ? (
                <AlertTriangle className="size-4 text-danger" aria-hidden />
              ) : (
                <LoaderCircle className="size-4 animate-spin text-muted" aria-hidden />
              )}
              <span className="truncate text-ink">{e.nom}</span>
              {e.erreur && <span className="text-xs text-danger">{e.erreur}</span>}
            </li>
          ))}
        </ul>
      )}
      {modifiable && (
        <>
          <button
            type="button"
            onClick={() => entree.current?.click()}
            className="flex items-center justify-center gap-2 rounded-md bg-canvas-app px-3 py-3 text-sm text-subtle transition-colors hover:bg-surface-soft hover:text-ink"
          >
            <UploadCloud className="size-4" aria-hidden />
            Glissez le fichier ici, ou cliquez
          </button>
          <input
            ref={entree}
            type="file"
            multiple
            className="sr-only"
            aria-label={`Déposer : ${emplacement.libelle}`}
            accept={FORMATS}
            onChange={(e) => {
              void deposer(e.target.files);
              e.target.value = "";
            }}
          />
        </>
      )}
    </div>
  );
}

function LigneDocument({
  fiche,
  document,
  modifiable,
  onFiche,
  onRanger,
  erreur,
}: {
  fiche: FicheImport;
  document: DocumentImport;
  modifiable: boolean;
  onFiche: (fiche: FicheImport) => void;
  onRanger: (document: DocumentImport, categorie: string) => void;
  erreur: string;
}) {
  async function ouvrir() {
    const blob = await telechargerDocumentImport(fiche.id, document.id);
    const lien = window.document.createElement("a");
    lien.href = URL.createObjectURL(blob);
    lien.download = nomCourt(document.nom_fichier);
    lien.click();
    URL.revokeObjectURL(lien.href);
  }

  const couleur =
    document.statut_traitement === "traite"
      ? "text-success"
      : document.statut_traitement === "illisible"
        ? "text-danger"
        : "text-warning";
  return (
    <li className="rounded-md bg-canvas-app px-3 py-2">
      <div className="flex items-center gap-2 text-sm">
        <FileText className="size-4 shrink-0 text-subtle" aria-hidden />
        <span className="min-w-0 flex-1 truncate text-ink" title={document.nom_fichier}>
          {nomCourt(document.nom_fichier)}
          <span className="ml-2 text-xs text-muted">{taille(document.taille)}</span>
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
      </div>
      {document.a_verifier ? (
        <div role="alert" className="mt-1 rounded-sm border border-danger-border bg-danger-subtle px-2 py-1 text-xs text-danger">
          <p className="flex items-center gap-1 font-medium">
            <AlertTriangle className="size-3.5" aria-hidden /> À vérifier : l&apos;OCR n&apos;a pas pu valider sa
            lecture (relue par deux modèles).
          </p>
          {(document.controles ?? []).length > 0 && (
            <ul className="mt-0.5 list-disc pl-5">
              {(document.controles ?? []).map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <p className={`mt-1 flex items-center gap-1 text-xs ${couleur}`}>
          {document.statut_traitement === "traite" && <Check className="size-3.5" aria-hidden />}
          <span className="font-medium">{libelleTraitement(document.statut_traitement)}</span>
          {document.resume && <span className="text-subtle">· {document.resume}</span>}
        </p>
      )}
      {modifiable && document.exercice !== null && document.emplacement.startsWith("reprise:") && (
        <RangerDocument document={document} erreur={erreur} onRanger={onRanger} />
      )}
    </li>
  );
}

/** AXE-970 : un document classé seul se range ailleurs dans son exercice.
 * Le déplacement est affiché tout de suite. */
function RangerDocument({
  document,
  erreur,
  onRanger,
}: {
  document: DocumentImport;
  erreur: string;
  onRanger: (document: DocumentImport, categorie: string) => void;
}) {
  return (
    <label className="mt-1 flex flex-wrap items-center gap-2 text-xs text-subtle">
      Ranger dans
      <select
        value={document.categorie}
        onChange={(e) => onRanger(document, e.target.value)}
        className="h-8 rounded-md border border-border bg-surface px-2 text-xs text-ink"
        aria-label={`Ranger ${document.nom_fichier} dans`}
      >
        {CATEGORIES_EXERCICE.map((c) => (
          <option key={c.cle} value={c.cle}>
            {c.libelle}
          </option>
        ))}
      </select>
      {document.origine_id && <span>· dans {archiveDe(document.nom_fichier) ?? "une archive"}</span>}
      {erreur && <span className="text-danger">{erreur}</span>}
    </label>
  );
}
