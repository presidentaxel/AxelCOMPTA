import assert from "node:assert/strict";
import { test } from "node:test";

import {
  ajouterAnnee,
  deplacerDocument,
  documentsVisibles,
  lireAnnee,
  ciblesPossibles,
  largeurs,
  libelleEtatBanque,
  archiveDe,
  nomCourt,
  versions,
  phraseDepot,
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
  type DocumentImport,
  type EmplacementImport,
  libelleStatut,
  fichesActives,
  dossiersIgnores,
  fichesSansDossier,
  nomChauffeur,
  nomEntreprise,
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

test("Entreprises compte les mêmes fiches que Toutes", () => {
  const fiches = [
    { id: "a", dossier_id: "D1", statut: "en_traitement" as const },
    { id: "b", dossier_id: null, statut: "en_traitement" as const },
    { id: "c", dossier_id: "D2", statut: "ignore" as const },
    { id: "d", dossier_id: "D3", statut: "traitee" as const },
  ];
  const dossiers = [{ dossier_id: "D1" }, { dossier_id: "D2" }, { dossier_id: "D3" }];
  const ignores = dossiersIgnores(fiches);
  assert.deepEqual([...ignores], ["D2"]);
  const presents = dossiers.filter((dossier) => !ignores.has(dossier.dossier_id));
  const seules = fichesSansDossier(fichesActives(fiches), presents);
  assert.deepEqual(
    seules.map((fiche) => fiche.id),
    ["b"],
  );
  assert.equal(presents.length + seules.length, fichesActives(fiches).length);
});

test("une entreprise sans fiche n'est pas ignorée", () => {
  assert.equal(dossiersIgnores([{ dossier_id: "D1", statut: "en_traitement" }]).has("D4"), false);
});

test("le nom d'entreprise prime sur celui du chauffeur", () => {
  assert.equal(nomEntreprise({ nom: "Dupont", prenom: "Karim", denomination: "MK DRIVING" }), "MK DRIVING");
  assert.equal(nomEntreprise({ nom: "Dupont", prenom: "Karim", denomination: null }), "Karim Dupont");
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

test("AXE-970 : ajouter un exercice depuis 2000, même avec des trous", () => {
  const aujourdhui = new Date(2026, 10, 17);
  assert.equal(lireAnnee("2019", aujourdhui), 2019);
  assert.equal(lireAnnee(" 2010 ", aujourdhui), 2010);
  assert.equal(lireAnnee("1999", aujourdhui), "Une année de clôture, de 2000 à 2026.");
  assert.equal(lireAnnee("2027", aujourdhui), "Une année de clôture, de 2000 à 2026.");
  assert.equal(lireAnnee("19", aujourdhui), "Une année de clôture, de 2000 à 2026.");
  assert.equal(ajouterAnnee("", 2019), "2019");
  assert.equal(ajouterAnnee("2019,2015", 2019), "2015,2019");
  assert.equal(ajouterAnnee("2019", 2010), "2010,2019");
});

test("AXE-970 : reclasser un document le déplace avant la réponse du serveur", () => {
  const document = (id: string, emplacement: string): DocumentImport => ({
    id,
    categorie: emplacement.split(":")[1] ?? "",
    libelle: id,
    exercice: Number(emplacement.split(":")[2]),
    emplacement,
    nom_fichier: `${id}.pdf`,
    taille: 10,
    depose_par: "a@x.fr",
    depose_le: "2026-01-01T00:00:00Z",
    statut_traitement: "a_traiter",
    resume: "",
  });
  const carte = (cle: string, documents: DocumentImport[] = []): EmplacementImport => ({
    cle,
    section: "reprise",
    libelle: cle,
    explication: "",
    attendu: false,
    documents,
  });
  const fiche = {
    emplacements: [
      carte("reprise:liasse:2019", [document("d1", "reprise:liasse:2019"), document("d2", "reprise:liasse:2019")]),
      carte("reprise:fec:2019", [document("deja", "reprise:fec:2019")]),
    ],
  };
  const deplace = deplacerDocument(fiche, "d1", "reprise:fec:2019");
  assert.deepEqual(
    deplace.emplacements.map((e) => [e.cle, e.documents.map((d) => d.id)]),
    [
      ["reprise:liasse:2019", ["d2"]],
      ["reprise:fec:2019", ["d1", "deja"]],
    ],
  );
  assert.equal(fiche.emplacements[0]?.documents.length, 2);
  const cree = deplacerDocument(fiche, "d1", "reprise:piece:2019");
  assert.equal(cree.emplacements.at(-1)?.libelle, "Pièces justificatives 2019");
  assert.equal(cree.emplacements.at(-1)?.documents[0]?.emplacement, "reprise:piece:2019");
  assert.equal(deplacerDocument(fiche, "absent", "reprise:fec:2019"), fiche);
  assert.equal(deplacerDocument(fiche, "d1", "reprise:liasse:2019"), fiche);
});

test("AXE-970 : une carte qui reçoit une archive replie ses pièces", () => {
  const pieces = Array.from({ length: 8 }, (_, i) => i);
  assert.deepEqual(documentsVisibles(pieces, false), { visibles: [0, 1, 2, 3, 4], caches: 3 });
  assert.deepEqual(documentsVisibles(pieces, true), { visibles: pieces, caches: 0 });
  assert.deepEqual(documentsVisibles([1, 2], false), { visibles: [1, 2], caches: 0 });
});

test("AXE-971 : après un dépôt, les doublons écartés sont nommés", () => {
  assert.equal(phraseDepot(3, []), "3 fichier(s) déposé(s), rangés par catégorie.");
  assert.equal(
    phraseDepot(1, ["a.pdf", "b.pdf", "c.pdf", "d.pdf"]),
    "1 fichier(s) déposé(s), rangés par catégorie. 4 déjà sur la fiche, écarté(s) : a.pdf, b.pdf, c.pdf….",
  );
});

test("AXE-972 : un document sorti d'une archive montre son nom et son archive", () => {
  const nom = "Clôture 2021-2022.zip/Clôture 2021-2022/archive_2022.zip/archive.zip/Grand Livre.pdf";
  assert.equal(nomCourt(nom), "Grand Livre.pdf");
  assert.equal(archiveDe(nom), "Clôture 2021-2022.zip");
  assert.equal(archiveDe("Grand Livre.pdf"), null);
});

test("AXE-972 : deux versions d'un grand livre sont signalées, pas l'impression du FEC", () => {
  const pdf = { resume: "À lire" };
  const impression = { resume: "Impression PDF du FEC : c'est le fichier texte du FEC qui se lit." };
  assert.equal(versions("grand_livre", [pdf, pdf]), 2);
  assert.equal(versions("fec", [{ resume: "FEC lu : 834 lignes" }, impression]), 1);
  assert.equal(versions("comptes_annuels", [pdf, pdf]), 0);
});

test("AXE-973 : la frise donne à chaque période sa part de la durée", () => {
  const tailles = largeurs([
    { debut: "2022-01-01", fin: "2022-12-31" },
    { debut: "2023-01-01", fin: "2023-01-01" },
    { debut: "2023-01-02", fin: "2025-12-31" },
  ]);
  assert.equal(tailles.length, 3);
  assert.ok(tailles[1] >= 1, "une période d'un jour reste visible");
  assert.ok(tailles[2] > tailles[0]);
  assert.equal(libelleEtatBanque("ecart"), "Écart au solde");
});

test("AXE-973 : un compte ne se rattache ni à lui-même ni à ce qu'il réunit déjà", () => {
  const compte = {
    cle: "digi:1", libelle: "Bred", origine: "digifactory" as const, suivi: true,
    periodes: [], soldes: [], incoherences: [], a_completer: [],
    reunit: [{ cle: "fec:5120020", libelle: "Bred (FEC)" }],
  };
  const connus = [
    { cle: "digi:1", libelle: "Bred" },
    { cle: "fec:5120020", libelle: "Bred (FEC)" },
    { cle: "fec:5120010", libelle: "Qonto" },
  ];
  assert.deepEqual(ciblesPossibles(compte, connus).map((c) => c.cle), ["fec:5120010"]);
});
