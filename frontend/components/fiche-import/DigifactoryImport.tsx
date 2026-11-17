"use client";

import { Check, LoaderCircle, Unplug } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { chercherDigifactoryImport, historiqueDigifactoryImport } from "@/lib/auth-gestionnaire";
import type { DigifactoryFiche } from "@/lib/fiches-import";

import type { Enregistrer } from "./ChampAuto";

/** AXE-947 : comme la synchro, la fiche cherche le contact Digifactory de la
 * personne (SIREN, entreprise, nom et prénom). Rien trouvé : la banque n'est
 * pas encore connectée. Relier = garder son numéro sur la fiche. */
function dateFrancaise(iso: string): string {
  const [annee, mois, jour] = iso.split("-").map(Number);
  return new Date(annee, mois - 1, jour).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export function DigifactoryImport({
  ficheId,
  contactActuel,
  historiqueActuel,
  cle,
  modifiable,
  enregistrer,
}: {
  ficheId: string;
  contactActuel: string;
  historiqueActuel: string;
  cle: string; // relance la recherche quand le nom ou le SIREN change
  modifiable: boolean;
  enregistrer: Enregistrer;
}) {
  const [resultat, setResultat] = useState<{ cle: string; vue: DigifactoryFiche } | null>(null);
  const [choisi, setChoisi] = useState(contactActuel);
  const [numero, setNumero] = useState(contactActuel);
  const [debut, setDebut] = useState<string | null>(null);
  const [historiqueLu, setHistoriqueLu] = useState<boolean | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    let actif = true;
    chercherDigifactoryImport(ficheId)
      .then((vue) => actif && setResultat({ cle, vue }))
      .catch(() => actif && setResultat({ cle, vue: { lu: false, contacts: [] } }));
    return () => {
      actif = false;
    };
  }, [ficheId, cle]);

  useEffect(() => {
    if (!choisi) return;
    let actif = true;
    historiqueDigifactoryImport(ficheId, choisi)
      .then(async (vue) => {
        if (!actif) return;
        setHistoriqueLu(vue.lu);
        setDebut(vue.debut);
        // Un champ déjà rempli reste : relier un autre contact le remplace.
        if (modifiable && vue.lu && vue.debut && !historiqueActuel) {
          await enregistrer({ debut_historique: vue.debut });
        }
      })
      .catch(() => actif && setHistoriqueLu(false));
    return () => {
      actif = false;
    };
  }, [choisi, enregistrer, ficheId, historiqueActuel, modifiable]);

  async function relier(contactNr: string) {
    const avant = choisi;
    setChoisi(contactNr); // tout de suite ; l'API confirme
    setNumero(contactNr);
    setErreur(null);
    try {
      await enregistrer({ contact_digifactory: contactNr });
    } catch (exception) {
      setChoisi(avant);
      setNumero(avant);
      setErreur(exception instanceof Error ? exception.message : "Erreur inattendue.");
      return;
    }
    if (!contactNr) {
      setDebut(null);
      setHistoriqueLu(null);
      return;
    }
    try {
      const vue = await historiqueDigifactoryImport(ficheId, contactNr);
      setHistoriqueLu(vue.lu);
      setDebut(vue.debut);
      if (vue.lu && vue.debut) await enregistrer({ debut_historique: vue.debut });
    } catch {
      setHistoriqueLu(false);
    }
  }

  const vue = resultat?.cle === cle ? resultat.vue : null;
  const dansLaListe = vue?.contacts.some((c) => c.contact_nr === choisi) ?? false;
  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-ink">Compte Digifactory</p>
      {vue === null ? (
        <p className="flex items-center gap-2 text-sm text-subtle">
          <LoaderCircle className="size-4 animate-spin" aria-hidden /> Recherche dans Digifactory…
        </p>
      ) : !vue.lu ? (
        <p className="text-sm text-subtle">Digifactory n&apos;a pas répondu : saisissez le numéro de contact s&apos;il est connu.</p>
      ) : vue.contacts.length === 0 ? (
        <p className="flex items-center gap-2 text-sm text-ink">
          <Unplug className="size-4 text-subtle" aria-hidden />
          Pas encore connecté à Digifactory : aucun contact à ce nom ni à ce SIREN.
        </p>
      ) : (
        <ul className="divide-y divide-hairline border-y border-border">
          {vue.contacts.map((c) => {
            const relie = choisi === c.contact_nr;
            return (
              <li key={c.contact_nr} className="flex items-center justify-between gap-3 py-3 text-sm">
                <span className="min-w-0">
                  <span className="font-medium text-ink">{c.nom}</span>
                  <span className="ml-2 text-subtle">
                    contact {c.contact_nr} · {c.raison}
                    {c.a_un_dossier && " · déjà un dossier dans Entreprises"}
                  </span>
                </span>
                {modifiable && (
                  <Button size="sm" variant={relie ? "secondary" : "ghost"} onClick={() => !relie && void relier(c.contact_nr)}>
                    {relie && <Check className="size-3.5" aria-hidden />}
                    {relie ? "Relié" : "Relier"}
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {modifiable && vue !== null && !dansLaListe && (
        <label htmlFor="contact-digifactory" className="block max-w-xs text-sm text-ink">
          Numéro de contact
          <Input
            id="contact-digifactory"
            className="mt-1.5"
            inputMode="numeric"
            value={numero}
            onChange={(e) => setNumero(e.target.value)}
            onBlur={() => {
              const saisi = numero.trim();
              if (saisi !== choisi) void relier(saisi);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") (e.target as HTMLInputElement).blur();
            }}
          />
        </label>
      )}
      {debut && (
        <p className="text-sm text-subtle">Première écriture Digifactory : {dateFrancaise(debut)}.</p>
      )}
      {historiqueLu && !debut && (
        <p className="text-sm text-subtle">Aucune écriture Digifactory pour ce contact.</p>
      )}
      {historiqueLu === false && (
        <p className="text-sm text-subtle">Digifactory n&apos;a pas donné la première écriture.</p>
      )}
      {erreur && <p role="alert" className="text-sm text-danger">{erreur}</p>}
    </div>
  );
}
