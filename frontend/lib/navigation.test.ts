import assert from "node:assert/strict";
import test from "node:test";

import { ENTREES_GESTIONNAIRE, cheminAffiche, entreeActive, initiales } from "./navigation";

test("une entrée est active sur sa page et sur ses sous-pages", () => {
  assert.equal(entreeActive("/portefeuille", "/portefeuille"), true);
  assert.equal(entreeActive("/expert/dossier-1", "/expert"), true);
});

test("une entrée n'est pas active sur une page voisine ou plus courte", () => {
  assert.equal(entreeActive("/equipes", "/equipe"), false);
  assert.equal(entreeActive("/", "/portefeuille"), false);
  assert.equal(entreeActive("/portefeuille", "/portefeuille/nouveau"), false);
});

test("un seul lien est actif pour un chemin donné", () => {
  for (const entree of ENTREES_GESTIONNAIRE) {
    const actives = ENTREES_GESTIONNAIRE.filter((autre) => entreeActive(`${entree.href}/x`, autre.href));
    assert.deepEqual(
      actives.map((autre) => autre.href),
      [entree.href],
    );
  }
});

test("la barre garde les sept entrées, dans l'ordre", () => {
  assert.deepEqual(
    ENTREES_GESTIONNAIRE.map((entree) => entree.libelle),
    [
      "Entreprises",
      "Mode expert",
      "Connexions bancaires",
      "Rappels",
      "Invitations",
      "Équipe",
      "Intégrations",
    ],
  );
});

test("les initiales sont les deux premières lettres de l'e-mail, en majuscules", () => {
  assert.equal(initiales("arthur@exemple.fr"), "AR");
  assert.equal(initiales("z@exemple.fr"), "Z@");
});

test("sans e-mail connu, l'avatar affiche AX", () => {
  assert.equal(initiales(""), "AX");
});

test("au clic, l'entrée visée est affichée avant l'arrivée de la page", () => {
  assert.equal(cheminAffiche("/portefeuille", { href: "/equipe", depuis: "/portefeuille" }), "/equipe");
});

test("sans attente, on montre le vrai chemin", () => {
  assert.equal(cheminAffiche("/portefeuille", null), "/portefeuille");
});

test("une attente périmée est ignorée : la page est arrivée ou une garde a redirigé", () => {
  assert.equal(cheminAffiche("/equipe", { href: "/equipe", depuis: "/portefeuille" }), "/equipe");
  assert.equal(cheminAffiche("/connexion", { href: "/equipe", depuis: "/portefeuille" }), "/connexion");
});
