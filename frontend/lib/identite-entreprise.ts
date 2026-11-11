// AXE-846 : le dirigeant saisit le siège, le capital et les associés de sa
// société. Ce module passe du formulaire (texte saisi) au corps envoyé à
// l'API, et l'inverse. Pur, testé. Le serveur revérifie tout.

import { lireMontantEuros } from "./montant";

export type Adresse = {
  numero: string;
  voie: string;
  code_postal: string;
  commune: string;
  pays: string;
};

export type Associe = {
  civilite: string;
  nom: string;
  prenoms: string;
  date_naissance: string; // AAAA-MM-JJ
  departement_naissance: string;
  commune_naissance: string;
  pays_naissance: string;
  adresse: Adresse;
  nb_titres: number;
  qualite: string;
};

export type Identite = {
  denomination: string;
  siren: string;
  nic: string;
  adresse_siege: Adresse;
  code_ape: string;
  activite: string;
  email: string;
  capital_social_cts: number;
  associes: Associe[];
};

export type IdentiteDossierVue = {
  identite: Identite | null;
  forme_juridique: string;
  associe_unique: boolean;
  qualite_par_defaut: string;
  siren_connu: string | null;
};

export type PersonneRegistre = {
  nom: string;
  prenoms: string;
  code_postal: string;
  commune: string;
  pays: string;
};

export type PreRemplissage = {
  siren: string;
  denomination: string;
  nic: string;
  adresse_siege: Adresse;
  code_ape: string;
  capital_social_cts?: number | null;
  personnes?: PersonneRegistre[];
};

/** Un associé tel que saisi : tout en texte, le nombre de titres compris. */
export type AssocieSaisi = Omit<Associe, "nb_titres"> & { nb_titres: string };

/** Le formulaire : tout en texte, le capital en euros. */
export type Formulaire = Omit<Identite, "capital_social_cts" | "associes"> & {
  capital_euros: string;
  associes: AssocieSaisi[];
};

export function adresseVide(): Adresse {
  return { numero: "", voie: "", code_postal: "", commune: "", pays: "France" };
}

export function associeVide(qualite: string): AssocieSaisi {
  return {
    civilite: "M",
    nom: "",
    prenoms: "",
    date_naissance: "",
    departement_naissance: "",
    commune_naissance: "",
    pays_naissance: "France",
    adresse: adresseVide(),
    nb_titres: "",
    qualite,
  };
}

function euros(centimes: number): string {
  const entiers = Math.floor(centimes / 100);
  const reste = centimes % 100;
  return reste === 0 ? String(entiers) : `${entiers},${String(reste).padStart(2, "0")}`;
}

/** Le formulaire de départ : l'identité déjà saisie, sinon un formulaire
 * vide avec le SIREN connu et un premier associé. */
export function formulaireDepuis(vue: IdentiteDossierVue): Formulaire {
  const identite = vue.identite;
  if (identite) {
    return {
      ...identite,
      capital_euros: euros(identite.capital_social_cts),
      associes: identite.associes.map((a) => ({ ...a, nb_titres: String(a.nb_titres) })),
    };
  }
  return {
    denomination: "",
    siren: vue.siren_connu ?? "",
    nic: "",
    adresse_siege: adresseVide(),
    code_ape: "",
    activite: "",
    email: "",
    capital_euros: "",
    associes: [associeVide(vue.qualite_par_defaut)],
  };
}

/** Le registre remplit ce qu'il sait ; une valeur qu'il ne donne pas ne
 * remplace jamais ce que le dirigeant a déjà saisi. La civilité, la date
 * de naissance, la rue du domicile et le nombre de titres n'y sont pas. */
export function appliquerRegistre(formulaire: Formulaire, registre: PreRemplissage): Formulaire {
  const garder = (saisi: string, trouve: string) => trouve || saisi;
  const siege = registre.adresse_siege;
  return {
    ...formulaire,
    siren: registre.siren,
    denomination: garder(formulaire.denomination, registre.denomination),
    nic: garder(formulaire.nic, registre.nic),
    code_ape: garder(formulaire.code_ape, registre.code_ape),
    capital_euros:
      formulaire.capital_euros ||
      (registre.capital_social_cts ? euros(registre.capital_social_cts) : ""),
    adresse_siege: {
      ...formulaire.adresse_siege,
      numero: garder(formulaire.adresse_siege.numero, siege.numero),
      voie: garder(formulaire.adresse_siege.voie, siege.voie),
      code_postal: garder(formulaire.adresse_siege.code_postal, siege.code_postal),
      commune: garder(formulaire.adresse_siege.commune, siege.commune),
    },
    associes: remplirAssocies(formulaire, registre.personnes ?? []),
  };
}

function remplirAssocies(formulaire: Formulaire, personnes: PersonneRegistre[]): AssocieSaisi[] {
  if (personnes.length === 0) return formulaire.associes;
  const dejaSaisi = formulaire.associes.some((a) => a.nom.trim() !== "" || a.prenoms.trim() !== "");
  if (dejaSaisi) return formulaire.associes;
  const qualite = formulaire.associes[0]?.qualite ?? "";
  return personnes.map((personne) => ({
    ...associeVide(qualite),
    nom: personne.nom,
    prenoms: personne.prenoms,
    adresse: {
      ...adresseVide(),
      code_postal: personne.code_postal,
      commune: personne.commune,
      pays: personne.pays || "France",
    },
  }));
}

export type Lecture = { corps: Identite; message: null } | { corps: null; message: string };

/** Le corps à envoyer, ou la première chose à corriger. Seules les
 * vérifications de forme sont ici ; le serveur décide du reste. */
export function lireFormulaire(formulaire: Formulaire): Lecture {
  const capital = lireMontantEuros(formulaire.capital_euros);
  if (capital.centimes === null) {
    return { corps: null, message: `Capital : ${capital.message}` };
  }
  const associes: Associe[] = [];
  for (const associe of formulaire.associes) {
    const titres = associe.nb_titres.trim();
    if (!/^\d+$/u.test(titres) || Number(titres) === 0) {
      return { corps: null, message: "Indiquez le nombre de titres de chaque associé." };
    }
    if (associe.date_naissance === "") {
      return { corps: null, message: "Indiquez la date de naissance de chaque associé." };
    }
    associes.push({ ...associe, nb_titres: Number(titres) });
  }
  const { capital_euros: _capital, ...reste } = formulaire;
  return {
    corps: { ...reste, siren: reste.siren.replace(/\s/gu, ""), capital_social_cts: capital.centimes, associes },
    message: null,
  };
}

/** L'adresse d'un associé unique est souvent celle du siège. */
export function copierAdresseDuSiege(formulaire: Formulaire, rang: number): Formulaire {
  return {
    ...formulaire,
    associes: formulaire.associes.map((a, i) =>
      i === rang ? { ...a, adresse: { ...formulaire.adresse_siege } } : a,
    ),
  };
}
