import assert from "node:assert/strict";
import test from "node:test";

import { aValider, chauffeursEvidents, ignores, phraseSynchro, synchroEnCours } from "./synchronisation";
import type { NouveauChauffeur, Synchronisation } from "./types";

const fini: Synchronisation = {
  statut: "fait",
  resultat: "2 nouveaux chauffeurs à valider, 148 opérations reçues",
  erreur: null,
  demandee_le: "2026-11-06T10:00:00Z",
  terminee_le: "2026-11-06T10:01:00Z",
};

test("phrase et état de la synchro", () => {
  assert.equal(phraseSynchro(null, (d) => d), null);
  assert.equal(phraseSynchro({ ...fini, statut: "en_cours" }, (d) => d), "Synchronisation en cours…");
  assert.equal(
    phraseSynchro(fini, () => "6 nov."),
    "Synchronisé (6 nov.) : 2 nouveaux chauffeurs à valider, 148 opérations reçues.",
  );
  assert.equal(
    phraseSynchro({ ...fini, statut: "echec", erreur: "401" }, (d) => d),
    "La synchronisation a échoué : 401.",
  );
  assert.equal(synchroEnCours({ ...fini, statut: "en_attente" }), true);
  assert.equal(synchroEnCours(fini), false);
});

const base: NouveauChauffeur = {
  contact_nr: "10",
  nom: "VTC NORD",
  siren: "111111111",
  forme: "SAS",
  exercice_debut: "2026-03-13",
  code_naf: "49.32Z",
  avertissements: [],
  cessee: false,
  decision: null,
};

test("tri des nouveaux chauffeurs", () => {
  const conseil = { ...base, contact_nr: "11", avertissements: ["activité 70.22Z"] };
  const cessee = { ...base, contact_nr: "12", cessee: true };
  const ignore = { ...base, contact_nr: "13", decision: "ignorer" as const };
  const accepte = { ...base, contact_nr: "14", decision: "ajouter" as const };
  const tous = [base, conseil, cessee, ignore, accepte];
  assert.deepEqual(aValider(tous).map((c) => c.contact_nr), ["10", "11"]);
  assert.deepEqual(chauffeursEvidents(tous).map((c) => c.contact_nr), ["10"]);
  assert.deepEqual(ignores(tous).map((c) => c.contact_nr), ["13"]);
});
