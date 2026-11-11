import assert from "node:assert/strict";
import test from "node:test";

import { ETAT_ATTENTE, ETAT_INJOIGNABLE, etatApresReponse } from "./desinscription";

test("un succès reprend le message de l'API, ou dit « C'est noté. »", () => {
  assert.deepEqual(etatApresReponse(true, { message: "Vous ne recevrez plus de rappels." }), {
    statut: "faite",
    message: "Vous ne recevrez plus de rappels.",
  });
  assert.deepEqual(etatApresReponse(true, {}), { statut: "faite", message: "C'est noté." });
});

test("un refus reprend le détail de l'API, ou dit que le lien n'est pas valable", () => {
  assert.deepEqual(etatApresReponse(false, { detail: "Lien expiré." }), {
    statut: "refusee",
    message: "Lien expiré.",
  });
  assert.deepEqual(etatApresReponse(false, {}), {
    statut: "refusee",
    message: "Ce lien n'est pas valable.",
  });
});

test("un refus ne prend jamais le message de succès", () => {
  assert.equal(etatApresReponse(false, { message: "C'est noté." }).message, "Ce lien n'est pas valable.");
});

test("l'attente et le serveur muet ont leur phrase", () => {
  assert.equal(ETAT_ATTENTE.statut, "attente");
  assert.equal(ETAT_INJOIGNABLE.statut, "injoignable");
});

test("une liste d'erreurs de validation ne devient pas le message affiché", () => {
  assert.deepEqual(etatApresReponse(false, { detail: [{ type: "missing", loc: ["query", "sig"], msg: "Field required" }] }), {
    statut: "refusee",
    message: "Ce lien n'est pas valable.",
  });
});
