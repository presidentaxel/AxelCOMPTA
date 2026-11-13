"use client";

// AXE-802 : le véhicule s'amortit. Le chauffeur déclare son achat (date de
// mise en service, durée proposée), la clôture passe la dotation. Une
// vente s'ajoute au registre, elle ne le réécrit pas.
import { useCallback, useEffect, useState } from "react";

import { Etat } from "@/components/Etat";
import { Montant } from "@/components/Montant";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import {
  cederImmobilisation,
  declarerImmobilisation,
  lireRegistreImmobilisations,
} from "@/lib/auth-chauffeur";
import { formatDate } from "@/lib/format";
import {
  dureeEnClair,
  lireDureeAnnees,
  phraseCession,
  type BienADeclarerVue,
  type ImmobilisationVue,
  type RegistreImmobilisationsVue,
} from "@/lib/immobilisations";
import { phrasePourChauffeur } from "@/lib/langage-chauffeur";
import { lireEuros } from "@/lib/saisie-chauffeur";

function messageDe(exception: unknown): string {
  return phrasePourChauffeur(
    exception instanceof ApiError ? exception.message : "L'enregistrement a échoué.",
  );
}

export function RegistreImmobilisations({
  dossierId,
  onChange,
}: {
  dossierId: string;
  onChange: () => void;
}) {
  const [registre, setRegistre] = useState<RegistreImmobilisationsVue | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [essai, setEssai] = useState(0);

  useEffect(() => {
    let actif = true;
    lireRegistreImmobilisations(dossierId)
      .then((lu) => {
        if (!actif) return;
        setErreur(null);
        setRegistre(lu);
      })
      .catch(() => {
        if (actif) setErreur("Le registre n'a pas pu être lu.");
      });
    return () => {
      actif = false;
    };
  }, [dossierId, essai]);

  const charger = useCallback(() => setEssai((n) => n + 1), []);

  function misAJour(suivant: RegistreImmobilisationsVue) {
    setRegistre(suivant);
    onChange();
  }

  if (erreur) return <Etat type="erreur" message={erreur} onReessayer={charger} />;
  if (registre === null) return null;
  if (registre.immobilisations.length === 0 && registre.a_declarer.length === 0) return null;

  return (
    <Card className="mt-8 p-4">
      <h2 className="text-base font-semibold text-ink">Véhicule et matériel</h2>
      <p className="mt-1 text-sm text-subtle">
        Un achat important s&apos;étale sur plusieurs années : chaque année, une part passe en
        charge à la clôture.
      </p>
      <ul className="mt-4">
        {registre.a_declarer.map((bien) => (
          <Declaration
            key={bien.ecriture_id}
            dossierId={dossierId}
            bien={bien}
            onFait={misAJour}
          />
        ))}
        {registre.immobilisations.map((fiche) => (
          <Fiche key={fiche.id} dossierId={dossierId} fiche={fiche} onFait={misAJour} />
        ))}
      </ul>
    </Card>
  );
}

function Declaration({
  dossierId,
  bien,
  onFait,
}: {
  dossierId: string;
  bien: BienADeclarerVue;
  onFait: (registre: RegistreImmobilisationsVue) => void;
}) {
  const [designation, setDesignation] = useState(bien.libelle);
  const [miseEnService, setMiseEnService] = useState(bien.date);
  const [duree, setDuree] = useState(String(bien.duree_proposee_mois / 12));
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  async function declarer() {
    const mois = lireDureeAnnees(duree);
    if (mois === null) {
      setErreur("Indiquez une durée entre 1 et 50 ans.");
      return;
    }
    setEnvoi(true);
    setErreur(null);
    try {
      onFait(
        await declarerImmobilisation(dossierId, {
          ecriture_id: bien.ecriture_id,
          designation,
          mise_en_service: miseEnService,
          duree_mois: mois,
        }),
      );
    } catch (exception) {
      setErreur(messageDe(exception));
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <li className="border-b border-hairline py-3">
      <p className="text-sm text-ink">
        Achat du {formatDate(bien.date)} : <Montant centimes={bien.base_cts} />
      </p>
      <div className="mt-2 grid gap-2 sm:grid-cols-3">
        <label className="text-sm text-subtle">
          Ce que c&apos;est
          <Input value={designation} onChange={(e) => setDesignation(e.target.value)} />
        </label>
        <label className="text-sm text-subtle">
          Mis en service le
          <Input type="date" value={miseEnService} onChange={(e) => setMiseEnService(e.target.value)} />
        </label>
        <label className="text-sm text-subtle">
          Durée (en années)
          <Input inputMode="decimal" value={duree} onChange={(e) => setDuree(e.target.value)} />
        </label>
      </div>
      <Button className="mt-2" disabled={envoi} onClick={() => void declarer()}>
        {envoi ? "Enregistrement…" : "Ajouter au registre"}
      </Button>
      {erreur && <p className="mt-1 text-xs text-danger">{erreur}</p>}
    </li>
  );
}

function Fiche({
  dossierId,
  fiche,
  onFait,
}: {
  dossierId: string;
  fiche: ImmobilisationVue;
  onFait: (registre: RegistreImmobilisationsVue) => void;
}) {
  const [vente, setVente] = useState(false);
  const [le, setLe] = useState("");
  const [prix, setPrix] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const resultat = phraseCession(fiche.plus_ou_moins_value_cts);

  async function ceder() {
    const lu = lireEuros(prix);
    if ("message" in lu || !le) {
      setErreur("message" in lu ? lu.message : "Indiquez la date de la vente.");
      return;
    }
    setErreur(null);
    try {
      onFait(await cederImmobilisation(dossierId, fiche.id, { le, prix_cts: lu.centimes }));
    } catch (exception) {
      setErreur(messageDe(exception));
    }
  }

  return (
    <li className="border-b border-hairline py-3">
      <p className="text-sm font-medium text-ink">{fiche.designation}</p>
      <p className="mt-1 text-sm text-subtle">
        Depuis le {formatDate(fiche.mise_en_service)}, sur {dureeEnClair(fiche.duree_mois)}. Part
        de cette année : <Montant centimes={fiche.dotation_exercice_cts} />. Valeur restante :{" "}
        <Montant centimes={fiche.valeur_nette_cts} />.
      </p>
      {fiche.cede_le ? (
        <p className="mt-1 text-sm text-subtle">
          Vendu le {formatDate(fiche.cede_le)}.{" "}
          {resultat && fiche.plus_ou_moins_value_cts !== 0 ? (
            <>
              {resultat} : <Montant centimes={Math.abs(fiche.plus_ou_moins_value_cts ?? 0)} />.
            </>
          ) : (
            resultat
          )}
        </p>
      ) : vente ? (
        <div className="mt-2 grid gap-2 sm:grid-cols-3">
          <label className="text-sm text-subtle">
            Vendu le
            <Input type="date" value={le} onChange={(e) => setLe(e.target.value)} />
          </label>
          <label className="text-sm text-subtle">
            Prix de vente
            <Input inputMode="decimal" value={prix} onChange={(e) => setPrix(e.target.value)} />
          </label>
          <Button className="self-end" onClick={() => void ceder()}>
            Enregistrer la vente
          </Button>
        </div>
      ) : (
        <Button variant="ghost" className="mt-1" onClick={() => setVente(true)}>
          Je l&apos;ai vendu
        </Button>
      )}
      {erreur && <p className="mt-1 text-xs text-danger">{erreur}</p>}
    </li>
  );
}
