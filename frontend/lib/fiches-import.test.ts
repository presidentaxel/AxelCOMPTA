import assert from "node:assert/strict";
import { test } from "node:test";

import {
  badgeStatut,
  basculerChoix,
  champsModifies,
  etatSection,
  libelleStatut,
  nomChauffeur,
  taille,
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
  assert.deepEqual(
    (["a_importer", "en_traitement", "traitee"] as const).map(badgeStatut),
    ["missing", "pending", "validated"],
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
