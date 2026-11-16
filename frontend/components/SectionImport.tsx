"use client";

import { useState } from "react";

import { ZoneDeTexte } from "@/components/ZoneDeTexte";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { basculerChoix, champsModifies, type ChampImport, type SectionImport } from "@/lib/fiches-import";

/** AXE-941 : les champs d'une catégorie de la fiche d'import. Seuls les
 * champs changés partent ; un champ vidé est effacé. */
export function FormulaireSectionImport({
  section,
  modifiable,
  onEnregistrer,
}: {
  section: SectionImport;
  modifiable: boolean;
  onEnregistrer: (champs: Record<string, string>) => Promise<void>;
}) {
  const [saisie, setSaisie] = useState<Record<string, string>>({});
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enregistre, setEnregistre] = useState(false);
  const modifies = champsModifies(section, saisie);

  async function enregistrer(evenement: React.FormEvent) {
    evenement.preventDefault();
    setEnvoi(true);
    setErreur(null);
    try {
      await onEnregistrer(modifies);
      setSaisie({});
      setEnregistre(true);
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Erreur inattendue.");
    } finally {
      setEnvoi(false);
    }
  }

  if (section.champs.length === 0) return null;
  return (
    <form onSubmit={enregistrer} className="max-w-2xl space-y-4">
      {section.champs.map((champ) => (
        <ChampSaisi
          key={champ.cle}
          champ={champ}
          valeur={saisie[champ.cle] ?? champ.valeur}
          desactive={!modifiable}
          onChange={(valeur) => {
            setEnregistre(false);
            setSaisie((avant) => ({ ...avant, [champ.cle]: valeur }));
          }}
        />
      ))}
      {erreur && <p role="alert" className="text-sm text-danger">{erreur}</p>}
      {enregistre && Object.keys(modifies).length === 0 && (
        <p role="status" className="text-sm text-subtle">Enregistré.</p>
      )}
      {modifiable && (
        <Button type="submit" disabled={envoi || Object.keys(modifies).length === 0}>
          {envoi ? "Enregistrement…" : "Enregistrer"}
        </Button>
      )}
    </form>
  );
}

const TYPES_INPUT: Partial<Record<ChampImport["type"], string>> = {
  date: "date",
  email: "email",
  telephone: "tel",
};

function ChampSaisi({
  champ,
  valeur,
  desactive,
  onChange,
}: {
  champ: ChampImport;
  valeur: string;
  desactive: boolean;
  onChange: (valeur: string) => void;
}) {
  const id = `champ-${champ.cle}`;
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-ink">
        {champ.libelle}
        {champ.obligatoire && <span className="ml-1 text-muted">(attendu)</span>}
      </label>
      <div className="mt-1">
        <Saisie id={id} champ={champ} valeur={valeur} desactive={desactive} onChange={onChange} />
      </div>
      {champ.aide && <p className="mt-1 text-xs text-muted">{champ.aide}</p>}
    </div>
  );
}

function Saisie({
  id,
  champ,
  valeur,
  desactive,
  onChange,
}: {
  id: string;
  champ: ChampImport;
  valeur: string;
  desactive: boolean;
  onChange: (valeur: string) => void;
}) {
  if (champ.type === "choix") {
    return (
      <Select
        id={id}
        value={valeur}
        disabled={desactive}
        onValueChange={onChange}
        placeholder="Choisir"
        options={champ.choix.map((c) => ({ value: c.cle, label: c.libelle }))}
      />
    );
  }
  if (champ.type === "multi") {
    return (
      <div id={id} className="flex flex-wrap gap-2" role="group" aria-label={champ.libelle}>
        {champ.choix.map((c) => {
          const coche = valeur.split(",").includes(c.cle);
          return (
            <Button
              key={c.cle}
              type="button"
              size="sm"
              variant={coche ? "secondary" : "ghost"}
              aria-pressed={coche}
              disabled={desactive}
              onClick={() => onChange(basculerChoix(valeur, c.cle))}
            >
              {c.libelle}
            </Button>
          );
        })}
      </div>
    );
  }
  if (champ.type === "long") {
    return <ZoneDeTexte id={id} rows={3} value={valeur} disabled={desactive} onChange={(e) => onChange(e.target.value)} />;
  }
  return (
    <Input
      id={id}
      type={TYPES_INPUT[champ.type] ?? "text"}
      inputMode={champ.type === "siren" || champ.type === "montant" ? "decimal" : undefined}
      placeholder={champ.type === "jour_mois" ? "31/12" : undefined}
      value={valeur}
      disabled={desactive}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
