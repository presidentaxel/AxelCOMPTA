"use client";

import { Check, LoaderCircle, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/Badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { chercherCompteRollee } from "@/lib/auth-gestionnaire";
import { lireListe, type ChampImport, type CompteRolleeRetenu } from "@/lib/fiches-import";
import { detailFiche, type FicheAnnuaireRollee } from "@/lib/liens-rollee";

import type { Enregistrer } from "./ChampAuto";

async function chercherTout(requetes: string[]): Promise<FicheAnnuaireRollee[]> {
  const listes = await Promise.all(
    requetes.filter((r) => r.trim().length >= 2).map((r) => chercherCompteRollee(r).catch(() => [])),
  );
  const uniques = new Map<string, FicheAnnuaireRollee>();
  for (const fiche of listes.flat()) uniques.set(fiche.rollee_user_id, fiche);
  return [...uniques.values()];
}

/** AXE-946 : les comptes Rollee du chauffeur. La fiche cherche seule avec le
 * nom du chauffeur et celui de l'entreprise ; si elle ne trouve pas, la
 * personne qui importe cherche à la main. Les comptes retenus restent sur la
 * fiche (le lien au dossier : AXE-942). */
export function RolleeImport({
  champ,
  nomChauffeur,
  entreprise,
  modifiable,
  enregistrer,
}: {
  champ: ChampImport;
  nomChauffeur: string;
  entreprise: string | null;
  modifiable: boolean;
  enregistrer: Enregistrer;
}) {
  // Optimistic UI : le choix s'affiche tout de suite, l'API confirme.
  const [retenus, setRetenus] = useState(() => lireListe<CompteRolleeRetenu>(champ.valeur));
  const [auto, setAuto] = useState<FicheAnnuaireRollee[] | null>(null);
  const [requete, setRequete] = useState("");
  const [trouves, setTrouves] = useState<{ requete: string; fiches: FicheAnnuaireRollee[] } | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    let actif = true;
    chercherTout([nomChauffeur, entreprise ?? ""]).then((r) => actif && setAuto(r));
    return () => {
      actif = false;
    };
  }, [nomChauffeur, entreprise]);

  const cherchee = requete.trim();
  useEffect(() => {
    if (cherchee.length < 2) return;
    const minuterie = window.setTimeout(
      () => chercherTout([cherchee]).then((fiches) => setTrouves({ requete: cherchee, fiches })),
      300,
    );
    return () => window.clearTimeout(minuterie);
  }, [cherchee]);
  const manuels = cherchee.length < 2 ? null : trouves?.requete === cherchee ? trouves.fiches : null;

  async function basculer(fiche: FicheAnnuaireRollee) {
    const deja = retenus.some((r) => r.rollee_user_id === fiche.rollee_user_id);
    const suivants = deja
      ? retenus.filter((r) => r.rollee_user_id !== fiche.rollee_user_id)
      : [...retenus, { rollee_user_id: fiche.rollee_user_id, nom: fiche.nom, plateformes: fiche.plateformes }];
    const avant = retenus;
    setRetenus(suivants);
    setErreur(null);
    try {
      await enregistrer({ comptes_rollee: suivants.length ? JSON.stringify(suivants) : "" });
    } catch (exception) {
      setRetenus(avant);
      setErreur(exception instanceof Error ? exception.message : "Erreur inattendue.");
    }
  }

  const idsRetenus = useMemo(() => new Set(retenus.map((r) => r.rollee_user_id)), [retenus]);
  return (
    <div className="space-y-5 sm:col-span-2">
      <div>
        <p className="text-sm font-medium text-ink">Comptes Rollee retenus</p>
        {retenus.length === 0 ? (
          <p className="mt-1 text-sm text-subtle">Aucun pour l&apos;instant : retenez-en un ci-dessous.</p>
        ) : (
          <ul className="mt-2 flex flex-wrap gap-2">
            {retenus.map((r) => (
              <li key={r.rollee_user_id}>
                <Badge variant="validated">
                  {r.nom} · {r.plateformes.join(", ") || "aucune plateforme"}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </div>
      <Resultats
        titre={`Trouvés dans Rollee pour « ${[nomChauffeur, entreprise].filter(Boolean).join(" », « ")} »`}
        fiches={auto}
        vide="Rien trouvé automatiquement : cherchez à la main."
        retenus={idsRetenus}
        modifiable={modifiable}
        onBasculer={basculer}
      />
      <div>
        <label htmlFor="recherche-rollee" className="text-sm font-medium text-ink">
          Chercher à la main
        </label>
        <div className="relative mt-1.5 max-w-md">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" />
          <Input
            id="recherche-rollee"
            className="pl-9"
            placeholder="Nom, prénom ou entreprise"
            value={requete}
            onChange={(e) => setRequete(e.target.value)}
          />
        </div>
      </div>
      {cherchee.length >= 2 && (
        <Resultats
          titre="Résultats"
          fiches={manuels}
          vide="Aucun user Rollee à ce nom."
          retenus={idsRetenus}
          modifiable={modifiable}
          onBasculer={basculer}
        />
      )}
      {erreur && <p role="alert" className="text-sm text-danger">{erreur}</p>}
    </div>
  );
}

function Resultats({
  titre,
  fiches,
  vide,
  retenus,
  modifiable,
  onBasculer,
}: {
  titre: string;
  fiches: FicheAnnuaireRollee[] | null;
  vide: string;
  retenus: Set<string>;
  modifiable: boolean;
  onBasculer: (fiche: FicheAnnuaireRollee) => void;
}) {
  if (fiches === null) {
    return (
      <p className="flex items-center gap-2 text-sm text-subtle">
        <LoaderCircle className="size-4 animate-spin" aria-hidden /> Recherche dans Rollee…
      </p>
    );
  }
  return (
    <div>
      <p className="text-sm text-subtle">{titre}</p>
      {fiches.length === 0 ? (
        <p className="mt-1 text-sm text-subtle">{vide}</p>
      ) : (
        <ul className="mt-2 divide-y divide-hairline border-y border-border">
          {fiches.map((fiche) => {
            const retenu = retenus.has(fiche.rollee_user_id);
            return (
              <li key={fiche.rollee_user_id} className="flex items-center justify-between gap-3 py-3">
                <div className="min-w-0 text-sm">
                  <p className="truncate font-medium text-ink">{fiche.nom}</p>
                  <p className="truncate text-subtle">
                    {detailFiche(fiche)}
                    {fiche.relie_a && ` · déjà relié à ${fiche.relie_a}`}
                  </p>
                </div>
                {modifiable && (
                  <Button size="sm" variant={retenu ? "secondary" : "ghost"} onClick={() => onBasculer(fiche)}>
                    {retenu && <Check className="size-3.5" aria-hidden />}
                    {retenu ? "Retenu" : "Retenir"}
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
