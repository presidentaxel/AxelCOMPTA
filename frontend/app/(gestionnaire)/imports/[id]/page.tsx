"use client";

import { ArrowLeft, ArrowRight, Check, Link2, LoaderCircle, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Badge } from "@/components/Badge";
import { SqueletteLignes } from "@/components/Squelette";
import { AssociesImport } from "@/components/fiche-import/AssociesImport";
import { ChampAuto, type Enregistrer } from "@/components/fiche-import/ChampAuto";
import { DigifactoryImport } from "@/components/fiche-import/DigifactoryImport";
import { EmplacementsSection } from "@/components/fiche-import/DocumentsImport";
import { EntrepriseImport } from "@/components/fiche-import/EntrepriseImport";
import { RolleeImport } from "@/components/fiche-import/RolleeImport";
import { Button } from "@/components/ui/button";
import {
  ErreurAuthGestionnaire,
  annulerFicheImport,
  completerFicheImport,
  deciderFicheImport,
  creerChauffeurImport,
  lireFicheImport,
} from "@/lib/auth-gestionnaire";
import {
  badgeStatut,
  etatSection,
  libelleStatut,
  nomChauffeur,
  progression,
  type ChampImport,
  type FicheImport,
  type SectionImport,
  valeurChamp,
} from "@/lib/fiches-import";
import { messageEchecChargement } from "@/lib/session";
import { useDroitGestionnaire } from "@/lib/use-droit";

const ENSEMBLE = "ensemble";

/** AXE-941, AXE-946 : une fiche d'import. Les catégories à gauche, avec leur
 * état ; la catégorie ouverte à droite. Changer de catégorie ne recharge
 * rien ; chaque champ s'enregistre seul. */
export default function FicheImportPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const droit = useDroitGestionnaire();
  const [fiche, setFiche] = useState<FicheImport | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [actif, setActif] = useState(() =>
    typeof window === "undefined"
      ? ENSEMBLE
      : (new URLSearchParams(window.location.search).get("section") ?? ENSEMBLE),
  );
  const file = useRef<Promise<unknown>>(Promise.resolve());

  useEffect(() => {
    lireFicheImport(id)
      .then(setFiche)
      .catch((exception) => {
        if (exception instanceof ErreurAuthGestionnaire) router.replace("/connexion");
        else setErreur(messageEchecChargement(exception, "La fiche n'a pas pu être chargée."));
      });
  }, [id, router]);

  /** Les enregistrements partent l'un après l'autre : une réponse ancienne
   * n'écrase jamais une plus récente. */
  const enregistrer: Enregistrer = useCallback(
    (champs) => {
      const suite = file.current.then(async () => setFiche(await completerFicheImport(id, champs)));
      file.current = suite.catch(() => undefined);
      return suite;
    },
    [id],
  );

  function ouvrir(cle: string) {
    setActif(cle);
    const url = cle === ENSEMBLE ? `/imports/${id}` : `/imports/${id}?section=${cle}`;
    window.history.replaceState(null, "", url);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  if (erreur) return <p role="alert" className="text-sm text-danger">{erreur}</p>;
  if (fiche === null) return <SqueletteLignes nombre={6} className="h-16" />;

  const modifiable = droit.ecriture;
  const section = fiche.sections_detail.find((s) => s.cle === actif) ?? null;
  return (
    <div className="space-y-6">
      <Link href="/imports" className="inline-flex items-center gap-1 text-sm text-subtle hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden /> Imports
      </Link>
      <EnTete fiche={fiche} ecriture={droit.ecriture} onFiche={setFiche} />
      <div className="grid gap-6 lg:grid-cols-[17rem_minmax(0,1fr)]">
        <Sommaire fiche={fiche} actif={actif} onOuvrir={ouvrir} />
        <div className="min-w-0 rounded-lg border border-border bg-canvas p-5 sm:p-6">
          {section === null ? (
            <VueEnsemble fiche={fiche} ecriture={droit.ecriture} onFiche={setFiche} onOuvrir={ouvrir} />
          ) : (
            <PanneauSection
              fiche={fiche}
              section={section}
              modifiable={modifiable}
              enregistrer={enregistrer}
              onFiche={setFiche}
              onSuivante={() => {
                const i = fiche.sections_detail.findIndex((s) => s.cle === section.cle);
                ouvrir(fiche.sections_detail[i + 1]?.cle ?? ENSEMBLE);
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function EnTete({
  fiche,
  ecriture,
  onFiche,
}: {
  fiche: FicheImport;
  ecriture: boolean;
  onFiche: (fiche: FicheImport) => void;
}) {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);

  async function decider(decision: "ignorer" | "reprendre") {
    try {
      onFiche(await deciderFicheImport(fiche.id, decision));
      setMessage(decision === "ignorer" ? "Fiche ignorée." : "Fiche remise dans les imports.");
    } catch (exception) {
      setMessage(exception instanceof Error ? exception.message : "Erreur inattendue.");
    }
  }

  async function annuler() {
    const qui = nomChauffeur(fiche);
    if (!window.confirm(`Annuler l'import de ${qui} ? La fiche sort de la liste des imports.`)) return;
    try {
      await annulerFicheImport(fiche.id);
      router.push("/imports");
    } catch (exception) {
      setMessage(exception instanceof Error ? exception.message : "Erreur inattendue.");
    }
  }

  const pourcent = progression(fiche);
  return (
    <header className="rounded-lg border border-border bg-canvas p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold text-ink">{nomChauffeur(fiche)}</h1>
            <Badge variant={badgeStatut(fiche.statut)}>{libelleStatut(fiche.statut)}</Badge>
          </div>
          <p className="mt-1 text-sm text-subtle">
            {fiche.denomination ?? "Entreprise à compléter"}
            {fiche.siren && ` · SIREN ${fiche.siren}`}
            {fiche.documents_a_lire > 0 &&
              ` · ${fiche.documents_a_lire} document${fiche.documents_a_lire > 1 ? "s" : ""} à lire`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => navigator.clipboard.writeText(window.location.href).then(() => setMessage("Lien copié."))}
          >
            <Link2 className="size-4" aria-hidden /> Copier le lien
          </Button>
          {ecriture && fiche.statut === "ignore" && (
            <Button size="sm" variant="secondary" onClick={() => void decider("reprendre")}>
              Remettre dans les imports
            </Button>
          )}
          {ecriture && fiche.statut !== "ignore" && (
            <Button size="sm" variant="ghost" onClick={() => void decider("ignorer")}>
              Ignorer
            </Button>
          )}
          {ecriture && (
            <Button size="sm" variant="ghost" onClick={() => void annuler()}>
              <Trash2 className="size-4" aria-hidden /> Annuler l&apos;import
            </Button>
          )}
        </div>
      </div>
      <div className="mt-5 flex items-center gap-3">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-soft" aria-hidden>
          <div className="h-full rounded-full bg-ink transition-all duration-300" style={{ width: `${pourcent}%` }} />
        </div>
        <span className="text-xs text-subtle">
          {fiche.sections_completes}/{fiche.sections} catégories complètes · statut calculé seul
        </span>
      </div>
      {message && <p role="status" className="mt-2 text-sm text-subtle">{message}</p>}
    </header>
  );
}

function Sommaire({
  fiche,
  actif,
  onOuvrir,
}: {
  fiche: FicheImport;
  actif: string;
  onOuvrir: (cle: string) => void;
}) {
  const entrees = [
    { cle: ENSEMBLE, libelle: "Vue d'ensemble", complet: null as boolean | null, manque: 0 },
    ...fiche.sections_detail.map((s) => ({ cle: s.cle, libelle: s.libelle, complet: s.complet, manque: s.manquants.length })),
  ];
  return (
    <nav aria-label="Catégories de la fiche" className="lg:sticky lg:top-6 lg:self-start">
      <ul className="flex gap-1 overflow-x-auto lg:flex-col">
        {entrees.map((e) => (
          <li key={e.cle} className="shrink-0">
            <button
              type="button"
              aria-current={actif === e.cle ? "page" : undefined}
              onClick={() => onOuvrir(e.cle)}
              className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors ${
                actif === e.cle ? "bg-surface-soft font-semibold text-ink" : "text-subtle hover:bg-surface-soft hover:text-ink"
              }`}
            >
              <PastilleEtat complet={e.complet} />
              <span className="flex-1 whitespace-nowrap">{e.libelle}</span>
              {e.complet === false && <span className="text-xs text-muted">{e.manque}</span>}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function PastilleEtat({ complet }: { complet: boolean | null }) {
  if (complet === null) return <span className="size-5" aria-hidden />;
  return complet ? (
    <span className="flex size-5 items-center justify-center rounded-full bg-success-subtle text-success">
      <Check className="size-3" aria-label="Complet" />
    </span>
  ) : (
    <span className="size-5 rounded-full border-2 border-dashed border-border-strong" aria-label="À compléter" />
  );
}

function VueEnsemble({
  fiche,
  ecriture,
  onFiche,
  onOuvrir,
}: {
  fiche: FicheImport;
  ecriture: boolean;
  onFiche: (fiche: FicheImport) => void;
  onOuvrir: (cle: string) => void;
}) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-ink">Vue d&apos;ensemble</h2>
        <p className="mt-1 text-sm text-subtle">Ce qui reste à compléter, catégorie par catégorie.</p>
      </div>
      <AjoutPortefeuille fiche={fiche} ecriture={ecriture} onFiche={onFiche} />
      <ul className="grid gap-3 md:grid-cols-2">
        {fiche.sections_detail.map((s) => (
          <li key={s.cle}>
            <button
              type="button"
              onClick={() => onOuvrir(s.cle)}
              className="group flex h-full w-full flex-col gap-2 rounded-lg border border-border p-4 text-left transition-colors hover:border-border-strong hover:bg-surface-soft"
            >
              <span className="flex items-center justify-between gap-2">
                <span className="font-medium text-ink">{s.libelle}</span>
                <Badge variant={s.complet ? "validated" : "pending"}>{etatSection(s)}</Badge>
              </span>
              <span className="text-xs text-subtle">
                {s.complet ? s.description : s.manquants.slice(0, 4).join(" · ") + (s.manquants.length > 4 ? " …" : "")}
              </span>
              <span className="mt-auto flex items-center gap-1 text-xs font-medium text-ink opacity-0 transition-opacity group-hover:opacity-100">
                Ouvrir <ArrowRight className="size-3" aria-hidden />
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function AjoutPortefeuille({
  fiche,
  ecriture,
  onFiche,
}: {
  fiche: FicheImport;
  ecriture: boolean;
  onFiche: (fiche: FicheImport) => void;
}) {
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const pret = fiche.manque_pour_creer.length === 0;

  if (fiche.dossier_id) {
    return (
      <div className="flex items-center gap-3 rounded-md border border-success-border bg-success-subtle px-4 py-3 text-sm text-ink">
        <Check className="size-4 text-success" aria-hidden />
        {fiche.dossier_cree
          ? `Chauffeur ajouté au portefeuille (${fiche.dossier_id}). Il sera invité dans son app plus tard.`
          : `Ajout au portefeuille en cours (${fiche.dossier_id}) : le dossier apparaît dans Entreprises d'ici une minute.`}
      </div>
    );
  }
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-canvas-app px-4 py-3">
      <p className="text-sm text-ink">
        {pret
          ? "La fiche suffit pour ajouter le chauffeur au portefeuille. Le reste peut se compléter ensuite."
          : `Pour ajouter le chauffeur au portefeuille : ${fiche.manque_pour_creer.join(", ")}.`}
      </p>
      {ecriture && (
        <Button
          size="sm"
          disabled={envoi || !pret}
          onClick={async () => {
            setEnvoi(true);
            setErreur(null);
            try {
              onFiche(await creerChauffeurImport(fiche.id));
            } catch (exception) {
              setErreur(exception instanceof Error ? exception.message : "Erreur inattendue.");
            } finally {
              setEnvoi(false);
            }
          }}
        >
          {envoi && <LoaderCircle className="size-4 animate-spin" aria-hidden />}
          Ajouter au portefeuille
        </Button>
      )}
      {erreur && <p role="alert" className="w-full text-sm text-danger">{erreur}</p>}
    </div>
  );
}

function PanneauSection({
  fiche,
  section,
  modifiable,
  enregistrer,
  onFiche,
  onSuivante,
}: {
  fiche: FicheImport;
  section: SectionImport;
  modifiable: boolean;
  enregistrer: Enregistrer;
  onFiche: (fiche: FicheImport) => void;
  onSuivante: () => void;
}) {
  return (
    <section className="space-y-6" aria-labelledby="titre-section">
      <div>
        <div className="flex flex-wrap items-center gap-3">
          <h2 id="titre-section" className="text-lg font-semibold text-ink">
            {section.libelle}
          </h2>
          <Badge variant={section.complet ? "validated" : "pending"}>{etatSection(section)}</Badge>
        </div>
        <p className="mt-1 text-sm text-subtle">{section.description}</p>
      </div>
      <ContenuSection fiche={fiche} section={section} modifiable={modifiable} enregistrer={enregistrer} />
      <EmplacementsSection
        fiche={fiche}
        section={section.cle}
        modifiable={modifiable}
        onFiche={onFiche}
        enregistrer={enregistrer}
      />
      {section.manquants.length > 0 && (
        <p className="text-sm text-subtle">
          Manque encore : <span className="text-ink">{section.manquants.join(", ")}</span>.
        </p>
      )}
      <div className="flex justify-end border-t border-border pt-4">
        <Button variant="secondary" onClick={onSuivante}>
          Catégorie suivante <ArrowRight className="size-4" aria-hidden />
        </Button>
      </div>
    </section>
  );
}

function ContenuSection({
  fiche,
  section,
  modifiable,
  enregistrer,
}: {
  fiche: FicheImport;
  section: SectionImport;
  modifiable: boolean;
  enregistrer: Enregistrer;
}) {
  if (section.cle === "entreprise") {
    return <EntrepriseImport fiche={fiche} section={section} modifiable={modifiable} enregistrer={enregistrer} />;
  }
  const champ = (c: ChampImport) => {
    if (c.type === "associes") {
      return <AssociesImport key={c.cle} champ={c} modifiable={modifiable} enregistrer={enregistrer} />;
    }
    if (c.type === "rollee") {
      return (
        <RolleeImport
          key={c.cle}
          champ={c}
          nomChauffeur={nomChauffeur({ ...fiche, denomination: null })}
          entreprise={fiche.denomination}
          modifiable={modifiable}
          enregistrer={enregistrer}
        />
      );
    }
    return (
      <ChampAuto
        key={c.cle}
        champ={c}
        modifiable={modifiable}
        duRegistre={fiche.depuis_registre.includes(c.cle)}
        enregistrer={enregistrer}
      />
    );
  };
  if (section.champs.length === 0) return null;
  return (
    <div className="grid gap-5 sm:grid-cols-2">
      {section.cle === "banque" && (
        <DigifactoryImport
          ficheId={fiche.id}
          contactActuel={valeurChamp(fiche, "contact_digifactory")}
          historiqueActuel={valeurChamp(fiche, "debut_historique")}
          cle={[fiche.siren, fiche.denomination, fiche.nom, fiche.prenom].join("|")}
          modifiable={modifiable}
          enregistrer={enregistrer}
        />
      )}
      {section.champs.filter((c) => c.cle !== "en_retard").map(champ)}
    </div>
  );
}
