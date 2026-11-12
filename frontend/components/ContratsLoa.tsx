"use client";

// AXE-803 : le chauffeur en LOA saisit son contrat une fois. La clôture
// étale le premier loyer majoré et la liasse annonce ce qu'il reste à payer.
// La levée d'option se déclare comme un achat, dans « Véhicule et matériel ».
import { useCallback, useEffect, useState } from "react";

import { Etat } from "@/components/Etat";
import { Montant } from "@/components/Montant";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { ajouterContratLoa, lireContratsLoa } from "@/lib/auth-chauffeur";
import { formatDate } from "@/lib/format";
import { phrasePourChauffeur } from "@/lib/langage-chauffeur";
import { lireDureeMois, phraseEngagement, type ContratLoaVue } from "@/lib/loa";
import { lireEuros } from "@/lib/saisie-chauffeur";

const CHAMPS = [
  ["loueur", "Loueur"],
  ["vehicule", "Véhicule"],
  ["debut", "Début du contrat"],
  ["duree", "Durée (en mois)"],
  ["loyer", "Loyer mensuel"],
  ["premier", "Premier loyer"],
  ["levee", "Prix de l'option d'achat"],
] as const;
type Champ = (typeof CHAMPS)[number][0];
type Lecture = { centimes: number } | { message: string };

function centimes(saisie: string, facultatif: boolean): Lecture {
  if (facultatif && saisie.trim() === "") return { centimes: 0 };
  return lireEuros(saisie);
}

export function ContratsLoa({ dossierId, onChange }: { dossierId: string; onChange: () => void }) {
  const [contrats, setContrats] = useState<ContratLoaVue[] | null>(null);
  const [erreurLecture, setErreurLecture] = useState<string | null>(null);
  const [essai, setEssai] = useState(0);
  const [ouvert, setOuvert] = useState(false);
  const [saisie, setSaisie] = useState<Record<Champ, string>>({
    loueur: "",
    vehicule: "",
    debut: "",
    duree: "36",
    loyer: "",
    premier: "",
    levee: "",
  });
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    let actif = true;
    lireContratsLoa(dossierId)
      .then((lus) => {
        if (!actif) return;
        setErreurLecture(null);
        setContrats(lus);
      })
      .catch(() => {
        if (actif) setErreurLecture("Les contrats n'ont pas pu être lus.");
      });
    return () => {
      actif = false;
    };
  }, [dossierId, essai]);

  const reessayer = useCallback(() => setEssai((n) => n + 1), []);

  async function enregistrer() {
    const duree = lireDureeMois(saisie.duree);
    const loyer = centimes(saisie.loyer, false);
    const premier = centimes(saisie.premier, true);
    const levee = centimes(saisie.levee, true);
    const refus = [loyer, premier, levee].find((x): x is { message: string } => "message" in x);
    if (duree === null || refus || !saisie.debut) {
      setErreur(refus?.message ?? "Indiquez la date de début et une durée entre 6 et 120 mois.");
      return;
    }
    setErreur(null);
    try {
      setContrats(
        await ajouterContratLoa(dossierId, {
          loueur: saisie.loueur,
          vehicule: saisie.vehicule,
          debut: saisie.debut,
          duree_mois: duree,
          loyer_mensuel_cts: "centimes" in loyer ? loyer.centimes : 0,
          premier_loyer_cts: "centimes" in premier ? premier.centimes : 0,
          prix_levee_cts: "centimes" in levee ? levee.centimes : 0,
        }),
      );
      setOuvert(false);
      onChange();
    } catch (exception) {
      setErreur(
        phrasePourChauffeur(
          exception instanceof ApiError ? exception.message : "L'enregistrement a échoué.",
        ),
      );
    }
  }

  if (erreurLecture) return <Etat type="erreur" message={erreurLecture} onReessayer={reessayer} />;
  if (contrats === null) return null;

  return (
    <Card className="mt-8 p-4">
      <h2 className="text-base font-semibold text-ink">Location avec option d&apos;achat (LOA)</h2>
      <ul className="mt-2">
        {contrats.map((c) => (
          <li key={c.id} className="border-b border-hairline py-3 text-sm">
            <p className="font-medium text-ink">
              {c.vehicule} — {c.loueur}
            </p>
            <p className="mt-1 text-subtle">
              Du {formatDate(c.debut)} au {formatDate(c.terme)}. {phraseEngagement(c.engagement_restant_cts)}{" "}
              : <Montant centimes={c.engagement_restant_cts} />.
            </p>
          </li>
        ))}
      </ul>
      {ouvert ? (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {CHAMPS.map(([champ, libelle]) => (
            <label key={champ} className="text-sm text-subtle">
              {libelle}
              <Input
                type={champ === "debut" ? "date" : "text"}
                inputMode={["duree", "loyer", "premier", "levee"].includes(champ) ? "decimal" : undefined}
                value={saisie[champ]}
                onChange={(e) => setSaisie((avant) => ({ ...avant, [champ]: e.target.value }))}
              />
            </label>
          ))}
          <Button className="self-end" onClick={() => void enregistrer()}>
            Enregistrer le contrat
          </Button>
        </div>
      ) : (
        <Button variant="ghost" className="mt-2" onClick={() => setOuvert(true)}>
          {contrats.length ? "Ajouter un autre contrat" : "Je roule en LOA"}
        </Button>
      )}
      {erreur && <p className="mt-1 text-xs text-danger">{erreur}</p>}
    </Card>
  );
}
