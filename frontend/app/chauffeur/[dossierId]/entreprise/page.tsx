"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Etat } from "@/components/Etat";
import { Squelette } from "@/components/Squelette";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { lireIdentite, lireRegistre, saisirIdentite } from "@/lib/auth-chauffeur";
import {
  appliquerRegistre,
  associeVide,
  copierAdresseDuSiege,
  formulaireDepuis,
  lireFormulaire,
  type Adresse,
  type AssocieSaisi,
  type Formulaire,
  type IdentiteDossierVue,
} from "@/lib/identite-entreprise";
import { phrasePourChauffeur } from "@/lib/langage-chauffeur";
import { messageEchecChargement } from "@/lib/session";

function message(exception: unknown, repli: string): string {
  return phrasePourChauffeur(exception instanceof Error ? exception.message : repli);
}

/** AXE-846 : le dirigeant renseigne le siège, le capital et les associés de
 * sa société. Sans eux, la liasse fiscale est refusée. Le SIREN pré-remplit
 * ce que le registre public connaît ; le reste se saisit. */
export default function MaSocietePage() {
  const { dossierId } = useParams<{ dossierId: string }>();
  const [vue, setVue] = useState<IdentiteDossierVue | null>(null);
  const [formulaire, setFormulaire] = useState<Formulaire | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(() => {
    setErreur(null);
    lireIdentite(dossierId)
      .then((lue) => {
        setVue(lue);
        setFormulaire(formulaireDepuis(lue));
      })
      .catch((exception: unknown) =>
        setErreur(messageEchecChargement(exception, "Impossible de lire votre société.")),
      );
  }, [dossierId]);

  useEffect(() => {
    // Premier chargement à l'ouverture de l'écran.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    charger();
  }, [charger]);

  if (erreur) return <Etat type="erreur" message={erreur} onReessayer={charger} />;
  if (!vue || !formulaire) {
    return (
      <Etat type="chargement" className="mt-0">
        <Squelette className="h-6 w-40" />
        <Squelette className="mt-6 h-64 w-full" />
      </Etat>
    );
  }
  return <Saisie dossierId={dossierId} vue={vue} formulaire={formulaire} onChange={setFormulaire} />;
}

function Saisie({
  dossierId,
  vue,
  formulaire,
  onChange,
}: {
  dossierId: string;
  vue: IdentiteDossierVue;
  formulaire: Formulaire;
  onChange: (formulaire: Formulaire) => void;
}) {
  const [envoi, setEnvoi] = useState(false);
  const [refus, setRefus] = useState<string | null>(null);
  const [enregistre, setEnregistre] = useState(false);

  async function enregistrer(evenement: React.FormEvent) {
    evenement.preventDefault();
    const lecture = lireFormulaire(formulaire);
    if (lecture.corps === null) {
      setRefus(lecture.message);
      return;
    }
    setEnvoi(true);
    setRefus(null);
    try {
      await saisirIdentite(dossierId, lecture.corps);
      setEnregistre(true);
    } catch (exception) {
      setRefus(message(exception, "L'enregistrement a échoué."));
    } finally {
      setEnvoi(false);
    }
  }

  if (enregistre) {
    return (
      <section aria-labelledby="titre-societe">
        <h1 id="titre-societe" className="text-xl font-semibold text-ink">
          Ma société
        </h1>
        <p className="mt-2 text-sm text-ink">C&apos;est enregistré. Votre bilan peut être préparé.</p>
        <Link href={`/chauffeur/${dossierId}`} className="mt-2 inline-flex min-h-11 items-center text-sm font-medium text-primary">
          Revenir à l&apos;accueil
        </Link>
      </section>
    );
  }

  return (
    <form onSubmit={enregistrer} aria-labelledby="titre-societe" className="space-y-6 text-sm text-ink">
      <div>
        <h1 id="titre-societe" className="text-xl font-semibold text-ink">
          Ma société
        </h1>
        <p className="mt-1 text-subtle">
          Ces informations figurent sur votre liasse fiscale. Vous les trouvez sur votre extrait Kbis
          et dans vos statuts.
        </p>
      </div>
      <Registre dossierId={dossierId} formulaire={formulaire} onChange={onChange} />
      <fieldset className="space-y-3">
        <legend className="font-medium">La société</legend>
        <Champ libelle="Nom de la société" valeur={formulaire.denomination} onChange={(v) => onChange({ ...formulaire, denomination: v })} />
        <Champ
          libelle="NIC du siège (5 derniers chiffres du SIRET)"
          valeur={formulaire.nic}
          inputMode="numeric"
          onChange={(v) => onChange({ ...formulaire, nic: v })}
        />
        <Champ
          libelle="Capital social (en euros)"
          valeur={formulaire.capital_euros}
          inputMode="decimal"
          onChange={(v) => onChange({ ...formulaire, capital_euros: v })}
        />
        <ChampsAdresse
          titre="Adresse du siège"
          adresse={formulaire.adresse_siege}
          onChange={(a) => onChange({ ...formulaire, adresse_siege: a })}
        />
      </fieldset>
      <Associes vue={vue} formulaire={formulaire} onChange={onChange} />
      {refus && <p className="text-danger">{refus}</p>}
      <Button type="submit" disabled={envoi} className="h-11 w-full">
        {envoi ? "Enregistrement…" : "Enregistrer ma société"}
      </Button>
    </form>
  );
}

function Registre({
  dossierId,
  formulaire,
  onChange,
}: {
  dossierId: string;
  formulaire: Formulaire;
  onChange: (formulaire: Formulaire) => void;
}) {
  const [recherche, setRecherche] = useState(false);
  const [retour, setRetour] = useState<string | null>(null);

  async function preRemplir() {
    setRecherche(true);
    setRetour(null);
    try {
      const trouve = await lireRegistre(dossierId, formulaire.siren);
      onChange(appliquerRegistre(formulaire, trouve));
      setRetour(
        "Rempli depuis le registre. Vérifiez chaque ligne : civilité, date de naissance, rue et nombre de titres restent à saisir.",
      );
    } catch (exception) {
      setRetour(message(exception, "Le registre n'a pas répondu. Saisissez à la main."));
    } finally {
      setRecherche(false);
    }
  }

  return (
    <div className="space-y-2">
      <Champ
        libelle="SIREN (9 chiffres)"
        valeur={formulaire.siren}
        inputMode="numeric"
        onChange={(v) => onChange({ ...formulaire, siren: v })}
      />
      <Button type="button" variant="secondary" className="h-11 w-full" disabled={recherche} onClick={preRemplir}>
        {recherche ? "Recherche…" : "Remplir depuis le registre"}
      </Button>
      {retour && <p className="text-subtle">{retour}</p>}
    </div>
  );
}

function Associes({
  vue,
  formulaire,
  onChange,
}: {
  vue: IdentiteDossierVue;
  formulaire: Formulaire;
  onChange: (formulaire: Formulaire) => void;
}) {
  function changer(rang: number, associe: AssocieSaisi) {
    onChange({ ...formulaire, associes: formulaire.associes.map((a, i) => (i === rang ? associe : a)) });
  }
  return (
    <fieldset className="space-y-4">
      <legend className="font-medium">{vue.associe_unique ? "L'associé unique" : "Les associés"}</legend>
      {formulaire.associes.map((associe, rang) => (
        <div key={rang} className="space-y-3 rounded-md border border-border p-3">
          <label className="block">
            Civilité
            <select
              value={associe.civilite}
              onChange={(e) => changer(rang, { ...associe, civilite: e.target.value })}
              className="mt-1 block h-11 w-full rounded-md border border-border bg-canvas px-3"
            >
              <option value="M">Monsieur</option>
              <option value="MME">Madame</option>
            </select>
          </label>
          <Champ libelle="Nom" valeur={associe.nom} onChange={(v) => changer(rang, { ...associe, nom: v })} />
          <Champ libelle="Prénoms" valeur={associe.prenoms} onChange={(v) => changer(rang, { ...associe, prenoms: v })} />
          <Champ
            libelle="Date de naissance"
            type="date"
            valeur={associe.date_naissance}
            onChange={(v) => changer(rang, { ...associe, date_naissance: v })}
          />
          <Champ
            libelle="Commune de naissance"
            valeur={associe.commune_naissance}
            onChange={(v) => changer(rang, { ...associe, commune_naissance: v })}
          />
          <Champ
            libelle="Département de naissance (ex. 75)"
            valeur={associe.departement_naissance}
            requis={false}
            onChange={(v) => changer(rang, { ...associe, departement_naissance: v })}
          />
          <Champ
            libelle="Nombre de titres détenus"
            valeur={associe.nb_titres}
            inputMode="numeric"
            onChange={(v) => changer(rang, { ...associe, nb_titres: v })}
          />
          <Champ libelle="Qualité (Président, Gérant, associé)" valeur={associe.qualite} onChange={(v) => changer(rang, { ...associe, qualite: v })} />
          <ChampsAdresse titre="Adresse personnelle" adresse={associe.adresse} onChange={(a) => changer(rang, { ...associe, adresse: a })} />
          <Button type="button" variant="secondary" className="h-11 w-full" onClick={() => onChange(copierAdresseDuSiege(formulaire, rang))}>
            Même adresse que le siège
          </Button>
          {formulaire.associes.length > 1 && (
            <Button
              type="button"
              variant="secondary"
              className="h-11 w-full"
              onClick={() => onChange({ ...formulaire, associes: formulaire.associes.filter((_, i) => i !== rang) })}
            >
              Retirer cet associé
            </Button>
          )}
        </div>
      ))}
      {!vue.associe_unique && (
        <Button
          type="button"
          variant="secondary"
          className="h-11 w-full"
          onClick={() => onChange({ ...formulaire, associes: [...formulaire.associes, associeVide("Associé")] })}
        >
          Ajouter un associé
        </Button>
      )}
    </fieldset>
  );
}

function ChampsAdresse({
  titre,
  adresse,
  onChange,
}: {
  titre: string;
  adresse: Adresse;
  onChange: (adresse: Adresse) => void;
}) {
  return (
    <div className="space-y-3">
      <p className="text-subtle">{titre}</p>
      <Champ libelle="Numéro" valeur={adresse.numero} requis={false} onChange={(v) => onChange({ ...adresse, numero: v })} />
      <Champ libelle="Voie" valeur={adresse.voie} onChange={(v) => onChange({ ...adresse, voie: v })} />
      <Champ
        libelle="Code postal"
        valeur={adresse.code_postal}
        inputMode="numeric"
        onChange={(v) => onChange({ ...adresse, code_postal: v })}
      />
      <Champ libelle="Commune" valeur={adresse.commune} onChange={(v) => onChange({ ...adresse, commune: v })} />
    </div>
  );
}

function Champ({
  libelle,
  valeur,
  onChange,
  type = "text",
  inputMode,
  requis = true,
}: {
  libelle: string;
  valeur: string;
  onChange: (valeur: string) => void;
  type?: string;
  inputMode?: "numeric" | "decimal";
  requis?: boolean;
}) {
  return (
    <label className="block">
      {libelle}
      <Input
        uiSize="lg"
        className="mt-1"
        type={type}
        inputMode={inputMode}
        required={requis}
        value={valeur}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}
