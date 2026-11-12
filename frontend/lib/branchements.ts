import type { Branchement } from "@/lib/auth-gestionnaire";

type Champ = {
  cle: string;
  libelle: string;
  type: "text" | "number" | "password" | "email" | "url" | "choix";
  facultatif?: boolean;
  /** Jeton, clé ou mot de passe : visible le temps de la saisie, jamais relu. */
  secret?: boolean;
  options?: { valeur: string; libelle: string }[];
};

/** AXE-872 : les types d'intégration qu'un portefeuille peut brancher, et
 * les champs de chacun. Les mêmes que `tenants/branchements.py` côté API. */
export const TYPES_BRANCHEMENT: Record<
  Branchement["type"],
  { nom: string; detail: string; fournisseur: string; champs: Champ[] }
> = {
  digifactory: {
    nom: "Digifactory",
    detail:
      "Apporte les comptes bancaires des entreprises. Un accès par compte Digifactory.",
    fournisseur: "digifactory",
    champs: [
      {
        cle: "jeton",
        libelle: "Jeton d'accès (X_DIGI_TOKEN)",
        type: "password",
        secret: true,
      },
      { cle: "url", libelle: "Adresse de l'API", type: "url" },
    ],
  },
  rollee: {
    nom: "Rollee",
    detail:
      "Lit les revenus Uber et Bolt. Plusieurs comptes Rollee pour une même compta : aucun n'est le défaut. Tant qu'un compte pro n'est pas relié, on les interroge tous.",
    fournisseur: "rollee",
    champs: [
      {
        cle: "jeton",
        libelle: "Jeton JWT (tableau de bord Rollee › Settings › JWT Token)",
        type: "password",
        secret: true,
      },
      {
        cle: "environnement",
        libelle: "Environnement du jeton",
        type: "choix",
        options: [
          { valeur: "sandbox", libelle: "Sandbox (essais, données fictives)" },
          { valeur: "production", libelle: "Production (vrais chauffeurs)" },
        ],
      },
    ],
  },
  mail: {
    nom: "E-mail",
    detail: "Votre serveur SMTP envoie les rappels aux chauffeurs.",
    fournisseur: "smtp",
    champs: [
      { cle: "hote", libelle: "Serveur SMTP", type: "text" },
      { cle: "port", libelle: "Port (587 ou 465)", type: "number" },
      { cle: "utilisateur", libelle: "Utilisateur", type: "text" },
      { cle: "mot_de_passe", libelle: "Mot de passe", type: "password", secret: true },
      { cle: "expediteur", libelle: "Adresse d'expédition", type: "email" },
    ],
  },
  sms: {
    nom: "SMS",
    detail: "Votre fournisseur de SMS (API HTTP) envoie les rappels courts.",
    fournisseur: "http",
    champs: [
      { cle: "url", libelle: "Adresse de l'API d'envoi", type: "url" },
      { cle: "cle_api", libelle: "Clé d'API", type: "password", secret: true },
      { cle: "expediteur", libelle: "Nom d'expéditeur", type: "text" },
    ],
  },
};

export const ORDRE_TYPES: Branchement["type"][] = [
  "digifactory",
  "rollee",
  "mail",
  "sms",
];
