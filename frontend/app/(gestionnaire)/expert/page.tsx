"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { EngagementExpert } from "@/components/EngagementExpert";
import { OperationsClassees } from "@/components/OperationsClassees";
import { Squelette } from "@/components/Squelette";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  annulerImputation,
  ErreurAuthGestionnaire,
  imputerExpert,
  lireFileExpert,
  ModeExpertRefuse,
} from "@/lib/auth-gestionnaire";
import {
  type EtatClassees,
  lireEtat,
  STATUTS,
  versRecherche,
  VUE_A_TRAITER,
} from "@/lib/classees";
import { remplacerSujetsDuDossier } from "@/lib/file-expert";
import { formatMontant } from "@/lib/format";
import { libelleMoyenPaiement } from "@/lib/moyens-paiement";
import {
  ecrireFiltreTag,
  gardeTag,
  libelleTag,
  lireFiltreTag,
  SANS_TAG,
  tagsPresents,
  TOUS_LES_TAGS,
} from "@/lib/tags";
import type { FileExpert, ImputationFaite, SujetExpert } from "@/lib/types";
import { useDroitGestionnaire } from "@/lib/use-droit";

const PAGE = 50;

const COTE: Record<SujetExpert["cote"], string> = {
  chauffeur: "À traiter par l'entreprise",
  gestionnaire: "À traiter par le gestionnaire",
};
const NATURE: Record<SujetExpert["nature"], string> = {
  a_trancher: "Opération",
  ticket: "Ticket",
  anomalie: "Anomalie",
};
const SENS = { debit: "Débit", credit: "Crédit" } as const;

/** L'imputation écrit dans la comptabilité : on le dit, on montre les lignes,
 * et on peut contre-passer. La file reste paginée, un compte par ligne. */
export default function ModeExpertPage() {
  const router = useRouter();
  const [file, setFile] = useState<FileExpert | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [erreurs, setErreurs] = useState<Record<string, string>>({});
  const [chargement, setChargement] = useState(true);
  const [compte, setCompte] = useState<Record<string, string>>({});
  const [enCours, setEnCours] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<SujetExpert | null>(null);
  // AXE-800 : motif obligatoire de chaque imputation, et de son annulation.
  const [motifs, setMotifs] = useState<Record<string, string>>({});
  const [motifAnnulation, setMotifAnnulation] = useState("");
  const [refus, setRefus] = useState<string | null>(null);
  const [succes, setSucces] = useState<{
    dossierId: string;
    libelle: string;
    imputation: ImputationFaite;
  } | null>(null);
  const [entreprise, setEntreprise] = useState("toutes");
  const [nature, setNature] = useState("toutes");
  const [tag, setTag] = useState(TOUS_LES_TAGS);
  const [visible, setVisible] = useState(PAGE);
  // AXE-823 : « À traiter » (la file) ou une vue des opérations déjà classées.
  const [vue, setVue] = useState<EtatClassees>(() => lireEtat(""));
  const droit = useDroitGestionnaire();

  useEffect(() => {
    // L'état des filtres vient de l'URL, lue une fois à l'arrivée.
    setVue(lireEtat(window.location.search));
  }, []);

  function changerVue(suivant: EtatClassees) {
    setVue(suivant);
    router.replace(`${window.location.pathname}${versRecherche(suivant)}`, { scroll: false });
  }

  useEffect(() => {
    // Filtre de tag partageable par l'URL (AXE-829), lu une fois à l'arrivée.
    setTag(lireFiltreTag(window.location.search));
  }, []);

  const retenirSuggestions = useCallback((sujets: SujetExpert[]) => {
    setCompte((actuel) => {
      const suite = { ...actuel };
      for (const sujet of sujets) {
        if (!suite[sujet.id] && sujet.compte_suggere) suite[sujet.id] = sujet.compte_suggere;
      }
      return suite;
    });
  }, []);

  const charger = useCallback(() => {
    lireFileExpert()
      .then((donnees) => {
        setFile(donnees);
        setErreur(null);
        setRefus(null);
        retenirSuggestions(donnees.sujets);
      })
      .catch((exception) => {
        if (exception instanceof ErreurAuthGestionnaire) {
          router.replace("/connexion");
        } else if (exception instanceof ModeExpertRefuse) {
          setFile(null);
          setRefus(exception.message);
        } else {
          setFile(null);
          setErreur("Impossible de charger la file.");
        }
      })
      .finally(() => setChargement(false));
  }, [retenirSuggestions, router]);

  useEffect(charger, [charger]);

  const entreprises = useMemo(() => {
    const noms = new Map<string, string>();
    for (const sujet of file?.sujets ?? []) noms.set(sujet.dossier_id, sujet.dossier_nom);
    return [...noms.entries()].sort((a, b) => a[1].localeCompare(b[1], "fr"));
  }, [file]);

  const filtres = useMemo(() => {
    return (file?.sujets ?? []).filter((sujet) => {
      if (entreprise !== "toutes" && sujet.dossier_id !== entreprise) return false;
      if (nature !== "toutes" && sujet.nature !== nature) return false;
      const tags = file?.tags_par_dossier?.[sujet.dossier_id] ?? [];
      return gardeTag({ tags }, tag);
    });
  }, [entreprise, file, nature, tag]);
  const tagsDeLaFile = useMemo(() => tagsPresents(file?.tags_par_dossier ?? {}), [file]);

  const page = filtres.slice(0, visible);

  async function imputer(sujet: SujetExpert) {
    const choisi = compte[sujet.id];
    const motif = (motifs[sujet.id] ?? "").trim();
    if (!choisi || !sujet.ecriture_id) return;
    if (motif.length < 3) {
      setErreurs((actuel) => ({ ...actuel, [sujet.id]: "Indiquez le motif de ce changement." }));
      return;
    }
    setEnCours(sujet.id);
    setConfirmation(null);
    setErreurs((actuel) => {
      const suite = { ...actuel };
      delete suite[sujet.id];
      return suite;
    });
    try {
      const imputation = await imputerExpert(sujet.dossier_id, sujet.ecriture_id, choisi, motif);
      setSucces({ dossierId: sujet.dossier_id, libelle: sujet.libelle, imputation });
      setFile((actuelle) =>
        actuelle && {
          ...actuelle,
          sujets: remplacerSujetsDuDossier(actuelle.sujets, sujet.dossier_id, imputation.sujets),
        },
      );
      retenirSuggestions(imputation.sujets);
    } catch (exception) {
      if (exception instanceof ErreurAuthGestionnaire) {
        router.replace("/connexion");
        return;
      }
      setErreurs((actuel) => ({
        ...actuel,
        [sujet.id]: exception instanceof Error ? exception.message : "Échec de l'imputation.",
      }));
    } finally {
      setEnCours(null);
    }
  }

  async function annuler() {
    if (!succes) return;
    if (motifAnnulation.trim().length < 3) {
      setErreur("Indiquez le motif de l'annulation.");
      return;
    }
    setEnCours("annuler");
    try {
      await annulerImputation(
        succes.dossierId,
        succes.imputation.ecriture_id,
        succes.imputation.contrepassation_id,
        motifAnnulation.trim(),
      );
      setSucces(null);
      setMotifAnnulation("");
      charger();
    } catch (exception) {
      if (exception instanceof ErreurAuthGestionnaire) {
        router.replace("/connexion");
        return;
      }
      setErreur(exception instanceof Error ? exception.message : "Échec de l'annulation.");
    } finally {
      setEnCours(null);
    }
  }

  function changerFiltre(suivant: "entreprise" | "nature" | "tag", valeur: string) {
    setVisible(PAGE);
    if (suivant === "entreprise") setEntreprise(valeur);
    else if (suivant === "nature") setNature(valeur);
    else {
      setTag(valeur);
      router.replace(ecrireFiltreTag(window.location.pathname, window.location.search, valeur), {
        scroll: false,
      });
    }
  }

  return (
    <div>
      <h1 className="text-[28px] font-bold tracking-tight text-ink">Mode expert</h1>
      <p className="mt-2 text-sm text-subtle">
        Libellés et montants des écritures encore ouvertes. « Imputer » écrit dans la
        comptabilité de l&apos;entreprise : une contre-passation, puis une nouvelle écriture.
        Le tableau de bord du portefeuille, lui, ne change pas.
      </p>
      {refus && <EngagementExpert raison={refus} onAccepte={charger} />}
      {erreur && (
        <div className="mt-6 flex items-center gap-3">
          <p className="text-sm text-danger">{erreur}</p>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => {
              setChargement(true);
              charger();
            }}
          >
            Réessayer
          </Button>
        </div>
      )}
      {succes && (
        <div className="mt-6 rounded-md border border-border bg-canvas p-4">
          <p className="text-sm font-medium text-ink">Écrit pour {succes.libelle}</p>
          <ul className="mt-2 space-y-1">
            {succes.imputation.lignes.map((ligne, index) => (
              <li key={`${ligne.compte}-${index}`} className="text-sm text-ink">
                {SENS[ligne.sens]} {ligne.compte}
                <span className="ml-2 tabular-nums text-subtle">
                  {formatMontant(ligne.montant_cts)}
                </span>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Input
              value={motifAnnulation}
              onChange={(e) => setMotifAnnulation(e.target.value)}
              placeholder="Motif de l'annulation"
              aria-label="Motif de l'annulation"
              className="max-w-sm"
            />
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={enCours === "annuler"}
              onClick={() => void annuler()}
            >
              Annuler
            </Button>
          </div>
        </div>
      )}
      {chargement && !file && (
        <div className="mt-8 space-y-3" aria-busy="true" aria-label="Chargement de la file">
          <Squelette className="h-10 w-full" />
          <Squelette className="h-16 w-full" />
          <Squelette className="h-16 w-full" />
          <Squelette className="h-16 w-full" />
        </div>
      )}
      <div className="mt-6 flex items-center gap-2 text-sm text-subtle">
        Statut
        <Select
          aria-label="Statut"
          value={vue.vue}
          onValueChange={(valeur) => changerVue({ ...vue, vue: valeur, page: "1" })}
          options={Object.entries(STATUTS).map(([id, libelle]) => ({ value: id, label: libelle }))}
          className="w-56"
        />
      </div>
      {vue.vue !== VUE_A_TRAITER && (
        <OperationsClassees
          etat={vue}
          comptes={file?.comptes ?? []}
          ecriture={droit.ecriture}
          onChanger={changerVue}
        />
      )}
      {vue.vue === VUE_A_TRAITER && file && (
        <>
          <div className="mt-6 flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-2 text-sm text-subtle">
              Entreprise
              <Select
                aria-label="Entreprise"
                value={entreprise}
                onValueChange={(valeur) => changerFiltre("entreprise", valeur)}
                options={[
                  { value: "toutes", label: "Toutes" },
                  ...entreprises.map(([id, nom]) => ({ value: id, label: nom })),
                ]}
                className="w-56"
              />
            </div>
            <div className="flex items-center gap-2 text-sm text-subtle">
              Nature
              <Select
                aria-label="Nature"
                value={nature}
                onValueChange={(valeur) => changerFiltre("nature", valeur)}
                options={[
                  { value: "toutes", label: "Toutes" },
                  ...(Object.keys(NATURE) as SujetExpert["nature"][]).map((id) => ({ value: id, label: NATURE[id] })),
                ]}
                className="w-48"
              />
            </div>
            {tagsDeLaFile.length > 0 && (
              <div className="flex items-center gap-2 text-sm text-subtle">
                Tag
                <Select
                  aria-label="Tag"
                  value={tag}
                  onValueChange={(valeur) => changerFiltre("tag", valeur)}
                  options={[
                    { value: TOUS_LES_TAGS, label: "Tous" },
                    { value: SANS_TAG, label: "Sans tag" },
                    ...tagsDeLaFile.map((nom) => ({ value: nom, label: libelleTag(nom) })),
                  ]}
                  className="w-48"
                />
              </div>
            )}
            <p className="text-sm text-subtle">
              {page.length} sur {filtres.length}
              {filtres.length !== file.sujets.length ? ` (${file.sujets.length} au total)` : ""}
            </p>
          </div>
          {filtres.length === 0 && (
            <p className="mt-8 text-sm text-subtle">
              {file.sujets.length === 0 ? "Rien en attente." : "Aucun sujet pour ce filtre."}
            </p>
          )}
          <ul className="mt-4">
            {page.map((sujet) => (
              <li key={sujet.id} className="border-b border-hairline py-3">
                <div className="flex items-baseline justify-between gap-4">
                  <p className="min-w-0">
                    <span className="block truncate text-base font-semibold text-ink">
                      {sujet.libelle}
                    </span>
                    <span className="mt-0.5 block text-sm text-subtle">
                      {sujet.dossier_nom} · {COTE[sujet.cote]} · {NATURE[sujet.nature]}
                    </span>
                    <span className="mt-0.5 block text-sm text-subtle">{sujet.detail}</span>
                    {sujet.moyen_paiement && (
                      <span className="mt-0.5 block text-sm text-subtle">
                        {libelleMoyenPaiement(sujet.moyen_paiement)}
                      </span>
                    )}
                    {sujet.compte_actuel && (
                      <span className="mt-0.5 block text-sm text-subtle">
                        Compte actuel {sujet.compte_actuel}
                        {sujet.compte_suggere ? ` · suggéré ${sujet.compte_suggere}` : ""}
                      </span>
                    )}
                  </p>
                  {sujet.montant_cts !== null && (
                    <span
                      className={`shrink-0 text-base font-semibold tabular-nums ${
                        sujet.montant_cts < 0 ? "text-amount-negative" : "text-amount-positive"
                      }`}
                    >
                      {formatMontant(sujet.montant_cts)}
                    </span>
                  )}
                </div>
                {sujet.nature === "anomalie" && (
                  <Link
                    href={`/anomalies/${sujet.dossier_id}`}
                    className="mt-3 inline-block text-sm font-medium text-signal hover:underline"
                  >
                    Instruire
                  </Link>
                )}
                {sujet.nature !== "anomalie" && sujet.imputable && sujet.ecriture_id && (
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <Select
                      aria-label={`Compte pour ${sujet.libelle}`}
                      value={compte[sujet.id] ?? ""}
                      onValueChange={(valeur) => setCompte((actuel) => ({ ...actuel, [sujet.id]: valeur }))}
                      placeholder="Compte"
                      options={file.comptes.map((choix) => ({
                        value: choix.compte,
                        label: `${choix.compte} — ${choix.libelle}`,
                      }))}
                      className="min-w-56"
                    />
                    <Input
                      value={motifs[sujet.id] ?? ""}
                      onChange={(e) =>
                        setMotifs((actuel) => ({ ...actuel, [sujet.id]: e.target.value }))
                      }
                      placeholder="Motif (obligatoire)"
                      aria-label={`Motif pour ${sujet.libelle}`}
                      className="max-w-xs"
                    />
                    <Button
                      type="button"
                      size="sm"
                      disabled={
                        !compte[sujet.id] ||
                        (motifs[sujet.id] ?? "").trim().length < 3 ||
                        enCours === sujet.id
                      }
                      onClick={() => setConfirmation(sujet)}
                    >
                      Imputer
                    </Button>
                    {sujet.nature === "ticket" && (
                      <span className="text-xs text-subtle">
                        Écrit en comptabilité sans le ticket.
                      </span>
                    )}
                  </div>
                )}
                {erreurs[sujet.id] && (
                  <p className="mt-2 text-sm text-danger">{erreurs[sujet.id]}</p>
                )}
                {confirmation?.id === sujet.id && (
                  <div className="mt-3 rounded-md border border-border bg-canvas-app p-4">
                    <p className="text-sm text-ink">
                      Écrire dans la comptabilité de {sujet.dossier_nom} : le compte{" "}
                      {compte[sujet.id]} remplace la contrepartie, le compte 512 reste. Les lignes
                      Débit et Crédit s&apos;affichent ensuite, et l&apos;écriture se défait.
                    </p>
                    <div className="mt-3 flex justify-end gap-2">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setConfirmation(null)}
                      >
                        Annuler
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        disabled={enCours === sujet.id}
                        onClick={() => void imputer(sujet)}
                      >
                        Écrire
                      </Button>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
          {visible < filtres.length && (
            <Button
              type="button"
              variant="secondary"
              className="mt-4"
              onClick={() => setVisible((actuel) => actuel + PAGE)}
            >
              Voir plus
            </Button>
          )}
        </>
      )}
    </div>
  );
}
