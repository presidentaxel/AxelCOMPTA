import assert from "node:assert/strict";
import test from "node:test";

import { urlLogo } from "./logos";

test("sans clé publiable, pas d'adresse de logo", () => {
  assert.equal(urlLogo("Uber", ""), null);
  assert.equal(urlLogo("  ", "pk_test"), null);
});

test("une plateforme connue part de son domaine, les autres de leur nom", () => {
  assert.equal(
    urlLogo("Bolt", "pk_test"),
    "https://img.logo.dev/bolt.eu?token=pk_test&size=64&format=png",
  );
  assert.equal(
    urlLogo("Heetch", "pk_test"),
    "https://img.logo.dev/heetch.com?token=pk_test&size=64&format=png",
  );
  assert.match(urlLogo("Autre", "pk_test") ?? "", /^https:\/\/img\.logo\.dev\/name\/Autre\?/);
});
