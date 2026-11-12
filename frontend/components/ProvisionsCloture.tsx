"use client";

// doc 06 §5 point 5 : le chauffeur sait qu'une charge de l'exercice n'est
// pas encore dans la banque. Il donne le montant. Le moteur ne décide pas
// à sa place quand provisionner.
//
// La lecture et la liste vide sont deux états. Tant que la lecture n'a pas
// réussi, aucun PUT ne part : sinon la seule ligne ajoutée remplacerait
// les provisions déjà saisies.
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";

import { Etat } from "@/components/Etat";
import { Montant } from "@/components/Montant";
import { Squelette } from "@/components/Squelette";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError } from "@/lib/api";
import {
  ErreurAuthChauffeur,
  enregistrerProvisionsCloture,
  lireProvisionsCloture,
} from "@/lib/auth-chauffeur";
import { CHARGES_CLOTURE, NOM_NATURE, phrasePourChauffeur } from "@/lib/langage-chauffeur";
import { lireEuros, listeAEnregistrer, listeSans, type LectureListe } from "@/lib/saisie-chauffeur";
import { messageEchecChargement } from "@/lib/session";
import type { ProvisionClotureVue } from "@/lib/types";

/** Les deux listes restent des `<select>` natifs, pas le `Select` de Radix :
 * sur téléphone, le chauffeur choisit dans la liste du système, et les tests
 * pilotent ce champ par son libellé (`selectOption`). Même gabarit que
 * `select-lg` de DESIGN.md : 44 px, 16 px (en dessous, iOS zoome), filet
 * `border-strong`, focus `signal`. */
const CHAMP_NATIF =
  "h-11 w-full rounded-md border border-border-strong bg-canvas px-3 text-base text-ink outline-none transition-colors duration-100 focus-visible:border-border-focus focus-visible:shadow-focus";

export function ProvisionsCloture({
  dossierId,
  onChange,
}: {
  dossierId: string;
  onChange: () => void;
}) {
  const [lecture, setLecture] = useState<LectureListe<ProvisionClotureVue>>({ statut: "en_cours" });
  const [nature, setNature] = useState<"cca" | "fnp">("fnp");
  const [compte, setCompte] = useState<string>(CHARGES_CLOTURE[0].compte);
  const [montant, setMontant] = useState("");
  const [libelle, setLibelle] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [suivi, setSuivi] = useState(dossierId);
  const ticket = useRef(0);

  if (suivi !== dossierId) {
    setSuivi(dossierId);
    setLecture({ statut: "en_cours" });
    setErreur(null);
  }

  const relire = useCallback(() => {
    const courant = ++ticket.current;
    lireProvisionsCloture(dossierId)
      .then((lues) => {
        if (ticket.current !== courant) return;
        setLecture({ statut: "pret", lignes: lues });
      })
      .catch((exception: unknown) => {
        if (ticket.current !== courant) return;
        setLecture({
          statut: "erreur",
          message: phrasePourChauffeur(
            messageEchecChargement(exception, "Impossible de charger ce qui est déjà saisi."),
          ),
        });
      });
  }, [dossierId]);

  useEffect(() => {
    relire();
  }, [relire]);

  async function envoyer(suivantes: ProvisionClotureVue[]): Promise<boolean> {
    setEnCours(true);
    setErreur(null);
    try {
      const enregistrees = await enregistrerProvisionsCloture(dossierId, suivantes);
      setLecture({ statut: "pret", lignes: enregistrees });
      onChange();
      return true;
    } catch (exception) {
      setErreur(
        phrasePourChauffeur(
          exception instanceof ErreurAuthChauffeur || exception instanceof ApiError
            ? exception.message
            : "Échec de l'enregistrement.",
        ),
      );
      return false;
    } finally {
      setEnCours(false);
    }
  }

  async function ajouter() {
    if (lecture.statut !== "pret") return;
    const lu = lireEuros(montant);
    if ("message" in lu || libelle.trim() === "") {
      setErreur("message" in lu ? lu.message : "Indiquez de quoi il s'agit.");
      return;
    }
    const suivantes = listeAEnregistrer(lecture, {
      nature,
      compte_charge: compte,
      centimes: lu.centimes,
      libelle: libelle.trim(),
    });
    if (suivantes === null) return;
    const ok = await envoyer(suivantes);
    if (!ok) return;
    setCompte(CHARGES_CLOTURE[0].compte);
    setMontant("");
    setLibelle("");
  }

  async function retirer(index: number) {
    const suivantes = listeSans(lecture, index);
    if (suivantes === null) return;
    await envoyer(suivantes);
  }

  const lignes = lecture.statut === "pret" ? lecture.lignes : [];
  const champs = useId();

  return (
    <section aria-labelledby="provisions-titre" className="mt-8">
      <Card>
        <p id="provisions-titre" className="text-base font-semibold text-ink">
          Une charge de cet exercice n&apos;est pas encore passée ?
        </p>
        <p className="mt-1 text-sm text-subtle">
          Donnez votre estimation. Elle sera prise dans la clôture. Rien n&apos;est deviné.
        </p>
        {lecture.statut === "en_cours" && <Squelette className="mt-3 h-13 w-full" />}
        {lecture.statut === "erreur" && (
          <Etat type="erreur" className="mt-3" message={lecture.message} onReessayer={relire} />
        )}
        {lignes.length > 0 && (
          <Table className="mt-3">
            <caption className="sr-only">Charges déjà saisies</caption>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Charge</TableHead>
                <TableHead montant>Estimation</TableHead>
                <TableHead>
                  <span className="sr-only">Action</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {lignes.map((ligne, index) => (
                <TableRow key={`${index}-${ligne.nature}-${ligne.compte_charge}-${ligne.libelle}`}>
                  <TableCell className="py-2 text-ink">
                    <span>
                      {NOM_NATURE[ligne.nature]} — {ligne.libelle}
                    </span>
                  </TableCell>
                  <TableCell montant className="py-2">
                    <Montant centimes={ligne.centimes} ton="neutre" />
                  </TableCell>
                  <TableCell className="py-1 text-right">
                    <Button
                      type="button"
                      variant="ghost"
                      size="lg"
                      disabled={enCours}
                      aria-label={`Retirer ${ligne.libelle}`}
                      onClick={() => void retirer(index)}
                    >
                      Retirer
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        <div className="mt-4 flex flex-col gap-3">
          <ChampEtiquete id={`${champs}-nature`} libelle="Nature">
            <select
              id={`${champs}-nature`}
              className={CHAMP_NATIF}
              value={nature}
              onChange={(evenement) => setNature(evenement.target.value === "cca" ? "cca" : "fnp")}
            >
              <option value="fnp">{NOM_NATURE.fnp}</option>
              <option value="cca">{NOM_NATURE.cca}</option>
            </select>
          </ChampEtiquete>
          <ChampEtiquete id={`${champs}-compte`} libelle="De quoi s'agit-il ?">
            <select
              id={`${champs}-compte`}
              className={CHAMP_NATIF}
              value={compte}
              onChange={(evenement) => setCompte(evenement.target.value)}
            >
              {CHARGES_CLOTURE.map((charge) => (
                <option key={charge.compte} value={charge.compte}>
                  {charge.libelle}
                </option>
              ))}
            </select>
          </ChampEtiquete>
          <ChampEtiquete id={`${champs}-montant`} libelle="Montant">
            <Input
              id={`${champs}-montant`}
              montant
              uiSize="lg"
              inputMode="decimal"
              placeholder="€"
              value={montant}
              onChange={(evenement) => setMontant(evenement.target.value)}
            />
          </ChampEtiquete>
          <ChampEtiquete id={`${champs}-libelle`} libelle="Libellé">
            <Input
              id={`${champs}-libelle`}
              uiSize="lg"
              value={libelle}
              onChange={(evenement) => setLibelle(evenement.target.value)}
            />
          </ChampEtiquete>
          <Button
            type="button"
            variant="secondary"
            size="lg"
            className="w-full"
            disabled={enCours || lecture.statut !== "pret"}
            onClick={() => void ajouter()}
          >
            Ajouter
          </Button>
        </div>
        {erreur && (
          <p role="alert" className="mt-3 text-sm text-danger">
            {erreur}
          </p>
        )}
      </Card>
    </section>
  );
}

/** Un champ avec son libellé visible : plus de placeholder qui disparaît à la
 * frappe, et le même texte nomme le champ pour les lecteurs d'écran. */
function ChampEtiquete({ id, libelle, children }: { id: string; libelle: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium text-ink">
        {libelle}
      </label>
      {children}
    </div>
  );
}
