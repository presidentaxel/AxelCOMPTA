/** Les mots de la page publique (AXE-949). Une seule source : les composants
 * n'écrivent aucune phrase de leur côté, et `landing-contenu.test.ts` vérifie
 * ici ce que le brief interdit (clients, prix, Rollee, application chauffeur,
 * signature RGS, annexes 2054 à 2059). Louis relit ces textes avant la mise
 * en ligne : toute modification passe par lui. */

/** Adresse publique du site, pour les aperçus de partage. */
export const URL_PUBLIQUE = "https://compta.axelproject.fr";

export const TITRE_PAGE = "AxeLCompta · Des dossiers VTC prêts à relire";

export const DESCRIPTION_PAGE =
  "Production comptable pour portefeuilles VTC : opérations classées, anomalies signalées avant la clôture, liasse préparée. L'expert-comptable décide.";

export const IMAGE_PARTAGE = {
  url: "/og-axelcompta.png",
  width: 1200,
  height: 630,
  alt: "AxeLCompta : des dossiers VTC prêts à relire",
};

export const HERO = {
  surtitre: "Production comptable · Dossiers VTC",
  titre: "Vos dossiers VTC arrivent",
  titreSurligne: "prêts à relire.",
  texte:
    "AxeL reçoit les opérations bancaires de chaque dossier, propose les écritures et signale ce qui sort de l'ordinaire avant la clôture. L'expert-comptable décide de chaque imputation incertaine.",
  action: "Demander un échange de 20 min",
  lien: "Voir l'ordre des opérations",
  garanties: "Dossiers cloisonnés, droits par rôle, double authentification.",
};

/** Un extrait de journal, inventé : l'aperçu ne montre jamais un vrai dossier. */
export type LigneJournal = {
  numero: string;
  libelle: string;
  compte: string;
  debitCentimes: number | null;
  creditCentimes: number | null;
  aImputer?: boolean;
};

export const EXTRAIT_JOURNAL = {
  titre: "Journal de banque · Dossier A",
  periode: "Novembre",
  lignes: [
    { numero: "0412", libelle: "Plein carburant", compte: "60622 Carburants", debitCentimes: 7017, creditCentimes: null },
    { numero: "0412", libelle: "TVA sur carburant", compte: "44566 TVA déductible", debitCentimes: 1403, creditCentimes: null },
    { numero: "0412", libelle: "Plein carburant", compte: "512 Banque", debitCentimes: null, creditCentimes: 8420 },
    {
      numero: "0413",
      libelle: "Péage autoroute",
      compte: "471 Compte d'attente",
      debitCentimes: 1260,
      creditCentimes: null,
      aImputer: true,
    },
    { numero: "0413", libelle: "Péage autoroute", compte: "512 Banque", debitCentimes: null, creditCentimes: 1260 },
  ] as LigneJournal[],
  legende:
    "Extrait illustratif, données fictives. Une écriture ne s'enregistre que si débit et crédit sont égaux.",
};

export const POUR_QUI = {
  surtitre: "Pour qui",
  titre: "Conçu pour ceux qui suivent des dossiers VTC.",
  profils: [
    {
      titre: "Cabinets d'expertise comptable",
      texte:
        "Les opérations courantes sont classées sans vous. Vous ne voyez que ce qui demande un jugement, et chaque imputation que vous faites porte votre motif.",
    },
    {
      titre: "Centrales et flottes VTC",
      texte:
        "Vous voyez où en est chaque dossier : à jour, en attente d'une décision, proche de la clôture. Le détail des comptes d'un chauffeur reste hors de votre vue.",
    },
  ],
};

export const FONCTIONS = {
  surtitre: "Ce que fait AxeL",
  titre: "De l'opération bancaire à la liasse, sur les mêmes écritures.",
  liste: [
    {
      nom: "Vue portefeuille",
      texte: "Chaque dossier avec son état : à traiter, à jour ou clôturé. On filtre, on trie, on cherche.",
    },
    {
      nom: "Mode expert",
      texte:
        "Une seule file pour tout ce qui reste à imputer, tous dossiers confondus. Chaque décision est motivée, journalisée et annulable.",
    },
    {
      nom: "Anomalies avant clôture",
      texte: "Un plein en double ou une dépense hors profil est signalé quand il arrive, pas en décembre.",
    },
    {
      nom: "Justificatifs",
      texte: "Les pièces se rattachent aux opérations. Une opération sans pièce ne bloque rien.",
    },
    {
      nom: "Clôture et liasse",
      texte: "TVA, résultat, liasse et FEC sortent des mêmes écritures, après des contrôles de cohérence.",
    },
    {
      nom: "Accès",
      texte:
        "Des droits par rôle et par membre, une double authentification pour les administrateurs et les experts, un journal des connexions.",
    },
  ],
};

export const ETAPES = {
  surtitre: "Ordre des opérations",
  titre: "Ce qui se passe, dans l'ordre.",
  liste: [
    {
      titre: "Les opérations arrivent",
      texte:
        "Les opérations bancaires de chaque dossier sont reçues et dédoublonnées, puis classées par des règles propres au VTC et par un modèle.",
    },
    {
      titre: "L'expert tranche",
      texte:
        "Ce qui est sûr est classé automatiquement. Le reste attend une décision, et les anomalies sont instruites au fil de l'année.",
    },
    {
      titre: "La clôture se prépare",
      texte:
        "Une fois les écritures validées, la TVA, le résultat, la liasse et le FEC sont produits et contrôlés.",
    },
  ],
};

export const ECHANGE = {
  surtitre: "Échange",
  titre: "20 minutes pour voir si AxeL convient à votre portefeuille.",
  texte: "Dites-nous qui vous êtes et ce que vous gérez. Nous répondons par e-mail pour fixer un créneau.",
  action: "Demander un échange de 20 min",
  envoi: "Envoi…",
  mentionAvant: "Ces informations servent à organiser cet échange, rien d'autre.",
  mentionLien: "Confidentialité",
  succes: "Merci, nous revenons vers vous par e-mail.",
  panne: "Le message n'est pas parti. Réessayez dans un instant.",
};

export const PIED = {
  signature: "AxeLCompta, production comptable pour dossiers VTC",
};

/** Tout le texte visible de la page, pour les vérifications de contenu. */
export function texteDeLaPage(): string {
  const profils = POUR_QUI.profils.flatMap((p) => [p.titre, p.texte]);
  const fonctions = FONCTIONS.liste.flatMap((f) => [f.nom, f.texte]);
  const etapes = ETAPES.liste.flatMap((e) => [e.titre, e.texte]);
  const journal = EXTRAIT_JOURNAL.lignes.flatMap((l) => [l.libelle, l.compte]);
  return [
    TITRE_PAGE,
    DESCRIPTION_PAGE,
    IMAGE_PARTAGE.alt,
    ...Object.values(HERO),
    ...Object.values(POUR_QUI).filter((v): v is string => typeof v === "string"),
    ...profils,
    ...Object.values(FONCTIONS).filter((v): v is string => typeof v === "string"),
    ...fonctions,
    ...Object.values(ETAPES).filter((v): v is string => typeof v === "string"),
    ...etapes,
    ...Object.values(ECHANGE),
    EXTRAIT_JOURNAL.titre,
    EXTRAIT_JOURNAL.legende,
    ...journal,
    PIED.signature,
  ].join("\n");
}

/** Centimes → « 1 234,56 » (colonne d'un journal, sans le symbole). */
export function formaterCentimes(centimes: number): string {
  const euros = Math.trunc(centimes / 100);
  const reste = String(centimes % 100).padStart(2, "0");
  return `${new Intl.NumberFormat("fr-FR").format(euros)},${reste}`;
}

/** Les deux totaux d'un extrait de journal, en centimes. */
export function totauxJournal(lignes: LigneJournal[]): { debit: number; credit: number } {
  return lignes.reduce(
    (somme, l) => ({
      debit: somme.debit + (l.debitCentimes ?? 0),
      credit: somme.credit + (l.creditCentimes ?? 0),
    }),
    { debit: 0, credit: 0 },
  );
}
