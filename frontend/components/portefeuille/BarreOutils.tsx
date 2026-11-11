"use client";

import { useId, useState, type ReactNode } from "react";

import { Squelette } from "@/components/Squelette";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { ReglageTags } from "@/lib/types";

import {
  LIBELLES_TRI,
  nombreDeFiltres,
  optionsBanque,
  optionsCompte,
  optionsEtape,
  optionsForme,
  optionsResultat,
  optionsTag,
  optionsTri,
  optionsTva,
  type EtatFiltres,
} from "./filtres";

type Props = {
  charge: boolean;
  /** Nombre d'entreprises visibles après filtres, tous groupes confondus. */
  visibles: number;
  etat: EtatFiltres;
  formes: string[];
  tvas: string[];
  reglageTags: ReglageTags | null;
  filtresActifs: boolean;
  /** Écrit un paramètre dans l'URL (`null` le retire). */
  onChanger: (maj: Record<string, string | null>) => void;
  onReinitialiser: () => void;
};

/** Barre d'outils : à gauche ce qu'on regarde, à droite la recherche et le
 * bouton « Filtres », qui ouvre le panneau des filtres et du tri.
 *
 * L'état reste dans l'URL (`onChanger` écrit les mêmes paramètres qu'avant) :
 * replier le panneau ne cache donc rien d'important, et il s'ouvre de lui-même
 * au chargement si un filtre est déjà posé. */
export function BarreOutils({
  charge,
  visibles,
  etat,
  formes,
  tvas,
  reglageTags,
  filtresActifs,
  onChanger,
  onReinitialiser,
}: Props) {
  const nombre = nombreDeFiltres(etat);
  const [ouvert, setOuvert] = useState(() => nombre > 0);
  const idPanneau = useId();

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        {charge ? (
          <p className="text-sm text-body">
            {visibles === 1 ? "1 entreprise" : `${visibles} entreprises`} · à traiter en premier, puis par{" "}
            {etat.tri === "nom" ? "nom" : LIBELLES_TRI[etat.tri].toLowerCase()}
          </p>
        ) : (
          <Squelette className="h-5 w-72" />
        )}
        <div className="flex items-center gap-2">
          <Input
            type="search"
            value={etat.recherche}
            onChange={(evenement) => onChanger({ q: evenement.target.value })}
            placeholder="Rechercher une entreprise"
            aria-label="Rechercher une entreprise"
            className="w-64"
          />
          <Button
            type="button"
            variant="secondary"
            aria-expanded={ouvert}
            aria-controls={idPanneau}
            onClick={() => setOuvert((avant) => !avant)}
          >
            Filtres
            {nombre > 0 && <span className="tabular-nums"> · {nombre}</span>}
          </Button>
          {filtresActifs && (
            <Button type="button" variant="ghost" onClick={onReinitialiser}>
              Réinitialiser
            </Button>
          )}
        </div>
      </div>
      {ouvert && (
        <div
          id={idPanneau}
          className="mt-3 grid grid-cols-2 gap-x-4 gap-y-4 rounded-md border border-border bg-canvas p-4 md:grid-cols-4"
        >
          <Champ libelle="Compte">
            {(id) => (
              <Select id={id} value={etat.compte} options={optionsCompte()} onValueChange={(v) => onChanger({ compte: v })} />
            )}
          </Champ>
          <Champ libelle="Résultat">
            {(id) => (
              <Select id={id} value={etat.resultat} options={optionsResultat()} onValueChange={(v) => onChanger({ resultat: v })} />
            )}
          </Champ>
          <Champ libelle="Forme">
            {(id) => (
              <Select id={id} value={etat.forme} options={optionsForme(formes)} onValueChange={(v) => onChanger({ forme: v })} />
            )}
          </Champ>
          <Champ libelle="TVA">
            {(id) => (
              <Select id={id} value={etat.tva} options={optionsTva(tvas)} onValueChange={(v) => onChanger({ tva: v })} />
            )}
          </Champ>
          <Champ libelle="Étape restante">
            {(id) => (
              <Select id={id} value={etat.etape} options={optionsEtape()} onValueChange={(v) => onChanger({ etape: v })} />
            )}
          </Champ>
          <Champ libelle="Comptes bancaires">
            {(id) => (
              <Select id={id} value={etat.banque} options={optionsBanque()} onValueChange={(v) => onChanger({ banque: v })} />
            )}
          </Champ>
          {reglageTags && (
            <Champ libelle="Tag">
              {(id) => (
                <Select id={id} value={etat.tag} options={optionsTag(reglageTags)} onValueChange={(v) => onChanger({ tag: v })} />
              )}
            </Champ>
          )}
          <Champ libelle="Trier par">
            {(id) => (
              <Select id={id} value={etat.tri} options={optionsTri()} onValueChange={(v) => onChanger({ tri: v })} />
            )}
          </Champ>
        </div>
      )}
    </div>
  );
}

/** Libellé visible au-dessus du champ, relié au déclencheur par `htmlFor`. */
function Champ({ libelle, children }: { libelle: string; children: (id: string) => ReactNode }) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[13px] leading-[1.38] font-medium text-subtle">
        {libelle}
      </label>
      {children(id)}
    </div>
  );
}
