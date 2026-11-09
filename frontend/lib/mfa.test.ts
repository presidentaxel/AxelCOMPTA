import assert from "node:assert/strict";
import test from "node:test";

import { codeNormalise, effacerChiffre, ecrireChiffres, facteurVerifie, imageDuQr } from "./mfa-code";

test("un code se lit sur six chiffres, espaces tolérés", () => {
  assert.equal(codeNormalise("123456"), "123456");
  assert.equal(codeNormalise(" 123 456 "), "123456");
  assert.equal(codeNormalise("12345"), null);
  assert.equal(codeNormalise("12345a"), null);
});

test("le QR SVG de Supabase devient une image", () => {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg"><rect fill="#000"/></svg>`;
  const image = imageDuQr(`<?xml version="1.0"?>\n${svg}`);
  assert.equal(image.startsWith("data:image/svg+xml;base64,"), true);
  const decode = Buffer.from(image.slice("data:image/svg+xml;base64,".length), "base64").toString();
  assert.equal(decode, svg);
  assert.equal(imageDuQr("data:image/png;base64,abcd"), "data:image/png;base64,abcd");
});

test("un chiffre avance, effacer une case vide revient en arrière", () => {
  const vides = ["", "", "", "", "", ""];
  const un = ecrireChiffres(vides, 0, "4");
  assert.deepEqual(un, { cases: ["4", "", "", "", "", ""], focus: 1 });

  const colle = ecrireChiffres(vides, 0, "12 34");
  assert.deepEqual(colle.cases, ["1", "2", "3", "4", "", ""]);
  assert.equal(colle.focus, 4);

  const plein = ["1", "2", "3", "4", "5", "6"];
  assert.deepEqual(effacerChiffre(plein, 5), {
    cases: ["1", "2", "3", "4", "5", ""],
    focus: 5,
  });
  assert.deepEqual(effacerChiffre(["1", "2", "3", "", "", ""], 3), {
    cases: ["1", "2", "", "", "", ""],
    focus: 2,
  });
});

test("seul un facteur TOTP vérifié compte", () => {
  assert.equal(facteurVerifie([]), null);
  assert.equal(facteurVerifie([{ id: "a", factor_type: "totp", status: "unverified" }]), null);
  assert.equal(facteurVerifie([{ id: "b", factor_type: "totp", status: "verified" }])?.id, "b");
});
