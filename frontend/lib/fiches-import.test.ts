import assert from "node:assert/strict";
import { test } from "node:test";

import {
  badgeStatut,
  basculerChoix,
  champsModifies,
  etatSection,
  basculerRetard,
  libelleTraitement,
  parExercice,
  phraseExercice,
  retardPossible,
  type ExerciceImport,
  type EmplacementImport,
  libelleStatut,
  fichesActives,
  fichesSansDossier,
  nomChauffeur,
  devinerCategorie,
  devinerExercice,
  ecrireComptesChoisis,
  fusionnerComptes,
  identifiantComplet,
  libelleIban,
  lireComptesChoisis,
  lireListe,
  progression,
  taille,
  totalParts,
  type Associe,
  type SectionImport,
} from "./fiches-import";

const SECTION: SectionImport = {
  cle: "dirigeant",
  libelle: "Dirigeant et contact",
  description: "",
  complet: false,
  manquants: ["E-mail"],
  champs: [
    { cle: "nom", libelle: "Nom", type: "texte", obligatoire: true, choix: [], aide: "", valeur: "Dupont" },
    { cle: "email", libelle: "E-mail", type: "email", obligatoire: true, choix: [], aide: "", valeur: "" },
  ],
};

test("une fiche sans dossier du portefeuille reste à part", () => {
  const fiches = [
    { dossier_id: "DIGI_1" },
    { dossier_id: null },
    { dossier_id: "SIREN_9" },
  ];
  assert.deepEqual(
    fichesSansDossier(fiches, [{ dossier_id: "DIGI_1" }]).map((fiche) => fiche.dossier_id),
    [null, "SIREN_9"],
  );
});

test("chaque statut a son libellé et son badge", () => {
  assert.equal(libelleStatut("a_importer"), "À importer");
  assert.equal(libelleStatut("ignore"), "Ignoré");
  assert.deepEqual(
    (["a_importer", "en_traitement", "traitee", "ignore"] as const).map(badgeStatut),
    ["missing", "pending", "validated", "closed"],
  );
});

test("une fiche ignorée sort de Toutes", () => {
  const fiches = [
    { statut: "a_importer" as const },
    { statut: "ignore" as const },
    { statut: "traitee" as const },
  ];
  assert.deepEqual(
    fichesActives(fiches).map((fiche) => fiche.statut),
    ["a_importer", "traitee"],
  );
});

test("le nom du chauffeur, ou son entreprise à défaut", () => {
  assert.equal(nomChauffeur({ nom: "Dupont", prenom: "Karim", denomination: "MK" }), "Karim Dupont");
  assert.equal(nomChauffeur({ nom: "", prenom: "", denomination: "MK DRIVING" }), "MK DRIVING");
});

test("une catégorie dit si elle est complète ou combien il manque", () => {
  assert.equal(etatSection(SECTION), "1 à compléter");
  assert.equal(etatSection({ complet: true, manquants: [] }), "Complet");
});

test("seuls les champs changés partent", () => {
  assert.deepEqual(champsModifies(SECTION, { nom: "Dupont ", email: "k@x.fr" }), { email: "k@x.fr" });
  assert.deepEqual(champsModifies(SECTION, {}), {});
});

test("cocher et décocher une plateforme", () => {
  assert.equal(basculerChoix("", "uber"), "uber");
  assert.equal(basculerChoix("uber,bolt", "uber"), "bolt");
});

test("la taille d'un fichier se lit en français", () => {
  assert.deepEqual([taille(500), taille(2048), taille(3_500_000)], ["500 o", "2 Ko", "3,3 Mo"]);
});

test("le type et l'exercice d'un document se devinent de son nom", () => {
  const permises = ["liasse", "fec", "balance", "grand_livre", "autre"];
  assert.equal(devinerCategorie("Liasse_2033_MK_2025.pdf", permises, "autre"), "liasse");
  assert.equal(devinerCategorie("552100554FEC20251231.txt", permises, "autre"), "fec");
  assert.equal(devinerCategorie("GL 2024.xlsx", permises, "autre"), "grand_livre");
  assert.equal(devinerCategorie("kbis.pdf", permises, "autre"), "autre"); // pas permis ici
  assert.equal(devinerExercice("FEC20251231.txt", [2024, 2025]), 2025);
  assert.equal(devinerExercice("scan.pdf", [2024, 2025]), null);
});

test("SIREN ou SIRET complet, et total des parts", () => {
  assert.equal(identifiantComplet("552 100 554"), "552100554");
  assert.equal(identifiantComplet("552 100 554 00013"), "55210055400013");
  assert.equal(identifiantComplet("55210"), null);
  const associes: Associe[] = [
    { prenom: "K", nom: "D", fonction: "president", pourcentage: "60,5" },
    { prenom: "L", nom: "D", fonction: "associe", pourcentage: "39.5" },
  ];
  assert.equal(totalParts(associes), 100);
  assert.deepEqual(lireListe("texte libre d'avant"), []);
  assert.equal(progression({ sections_completes: 3, sections: 7 }), 43);
});

test("les emplacements se rangent par exercice, le plus récent d'abord", () => {
  const e = (cle: string): EmplacementImport => ({
    cle,
    section: cle.split(":")[0],
    libelle: cle,
    explication: "",
    attendu: true,
    documents: [],
  });
  const groupes = parExercice([e("reprise:liasse:2024"), e("reprise:autre"), e("reprise:liasse:2025")]);
  assert.deepEqual(
    groupes.map(([annee, liste]) => [annee, liste.map((x) => x.cle)]),
    [
      [2025, ["reprise:liasse:2025"]],
      [2024, ["reprise:liasse:2024"]],
      [null, ["reprise:autre"]],
    ],
  );
  assert.equal(libelleTraitement("traite"), "Lu automatiquement");
});

test("chaque exercice dit son rôle pour la reprise, et le retard se coche", () => {
  const e: ExerciceImport = {
    annee: 2026,
    debut: "2025-10-01",
    fin: "2026-09-30",
    etat: "clos",
    role: "a_declarer",
    echeance: "2027-01-15",
    en_retard: false,
  };
  assert.equal(phraseExercice(e), "À déclarer par nous : liasse avant le 15/01/2027.");
  assert.equal(retardPossible(e), false);
  assert.equal(retardPossible({ ...e, role: "source" }), true);
  assert.equal(basculerRetard("", 2025), "2025");
  assert.equal(basculerRetard("2024,2025", 2025), "2024");
});

test("un compte se marque pro ou perso, et une ancienne ligne se relit", () => {
  const legacy = lireComptesChoisis("Compte courant (retenu)\nLivret (écarté)");
  assert.deepEqual(
    legacy.map((compte) => [compte.nom, compte.usage]),
    [
      ["Compte courant", "pro"],
      ["Livret", "perso"],
    ],
  );
  const live = [
    {
      id: "12",
      nom: "Compte courant",
      banque: "Qonto",
      iban: "FR7630006000011234567890189",
      professionnel: true,
    },
  ];
  const fusion = fusionnerComptes(live, legacy);
  assert.equal(fusion[0]?.usage, "pro");
  assert.equal(libelleIban(live[0].iban, ""), "FR76 3000 6000 0112 3456 7890 189");
  const choisi = ecrireComptesChoisis([{ ...fusion[0], usage: "perso" }]);
  assert.deepEqual(lireComptesChoisis(choisi), [
    { id: "12", nom: "Compte courant", banque: "Qonto", fin: "0189", usage: "perso" },
  ]);
  assert.equal(libelleIban("", "0189"), "•••• 0189");
});
