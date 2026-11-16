"use client";

import { Building2, LoaderCircle, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Input } from "@/components/ui/input";
import { identifiantComplet, valeurChamp, type FicheImport, type SectionImport } from "@/lib/fiches-import";

import { ChampAuto, type Enregistrer } from "./ChampAuto";

/** AXE-946 : « SIREN ou SIRET ». Dès que le numéro est complet, la fiche
 * l'enregistre et l'API interroge l'INSEE et le RNE ; les champs se
 * remplissent et restent modifiables. */
export function EntrepriseImport({
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
  const actuel = valeurChamp(fiche, "siret") || valeurChamp(fiche, "siren");
  const [saisie, setSaisie] = useState(actuel);
  const [recherche, setRecherche] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const derniere = useRef(actuel);

  useEffect(() => {
    const numero = identifiantComplet(saisie);
    if (!numero || numero === derniere.current || !modifiable) return;
    const minuterie = window.setTimeout(async () => {
      derniere.current = numero;
      setRecherche(true);
      setErreur(null);
      try {
        await enregistrer({ siren: numero });
      } catch (exception) {
        setErreur(exception instanceof Error ? exception.message : "Erreur inattendue.");
      } finally {
        setRecherche(false);
      }
    }, 400);
    return () => window.clearTimeout(minuterie);
  }, [saisie, modifiable, enregistrer]);

  const autres = section.champs.filter((c) => c.cle !== "siren" && c.cle !== "siret");
  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-border bg-canvas-app p-4">
        <label htmlFor="identifiant-entreprise" className="text-sm font-medium text-ink">
          SIREN ou SIRET
        </label>
        <div className="relative mt-1.5">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" />
          <Input
            id="identifiant-entreprise"
            inputMode="numeric"
            uiSize="lg"
            className="pl-9"
            placeholder="9 ou 14 chiffres"
            value={saisie}
            disabled={!modifiable}
            onChange={(e) => setSaisie(e.target.value)}
          />
        </div>
        <ResultatRegistre fiche={fiche} recherche={recherche} erreur={erreur} />
      </div>
      <div className="grid gap-5 sm:grid-cols-2">
        {autres.map((champ) => (
          <ChampAuto
            key={`${champ.cle}:${champ.valeur}`}
            champ={champ}
            modifiable={modifiable}
            duRegistre={fiche.depuis_registre.includes(champ.cle)}
            enregistrer={enregistrer}
          />
        ))}
      </div>
    </div>
  );
}

function ResultatRegistre({
  fiche,
  recherche,
  erreur,
}: {
  fiche: FicheImport;
  recherche: boolean;
  erreur: string | null;
}) {
  if (recherche) {
    return (
      <p role="status" className="mt-3 flex items-center gap-2 text-sm text-subtle">
        <LoaderCircle className="size-4 animate-spin" aria-hidden /> Recherche à l&apos;INSEE et au RNE…
      </p>
    );
  }
  if (erreur) return <p role="alert" className="mt-3 text-sm text-danger">{erreur}</p>;
  if (!fiche.registre_lu_le) {
    return (
      <p className="mt-3 text-sm text-subtle">
        La recherche part toute seule dès que le numéro est complet. Sans SIREN, tout se saisit à la main.
      </p>
    );
  }
  const forme = valeurChamp(fiche, "forme_juridique");
  return (
    <div className="mt-3 flex items-start gap-3 rounded-md border border-border bg-canvas p-3">
      <Building2 className="mt-0.5 size-5 shrink-0 text-subtle" aria-hidden />
      <div className="text-sm">
        <p className="font-medium text-ink">
          {fiche.denomination ?? "Dénomination inconnue"}
          {forme && <span className="font-normal text-subtle"> · {forme}</span>}
        </p>
        <p className="text-subtle">
          Trouvée {fiche.registre_sources.map((s) => (s === "rne" ? "au RNE" : "à l'INSEE")).join(" et ")} le{" "}
          {new Date(fiche.registre_lu_le).toLocaleDateString("fr-FR")}. Vérifiez et corrigez si besoin.
        </p>
      </div>
    </div>
  );
}
