import { expect, test, type Page, type Route } from "@playwright/test";

/** Jeton non signé : le navigateur ne vérifie que la date d'expiration. */
function jeton(claims: Record<string, unknown>): string {
  const coder = (valeur: object) => Buffer.from(JSON.stringify(valeur)).toString("base64");
  return `${coder({ alg: "none", typ: "JWT" })}.${coder(claims)}.signature`;
}

const DOSSIER = {
  dossier_id: "DEMO_sophie",
  nom: "Sophie Martin",
  tva_recettes_regime: "franchise",
  plateformes: [],
  exercice_debut: "2026-01-01",
  exercice_fin: "2026-12-31",
  ca_ht_cts: 100_00,
  charges_cts: 40_00,
  resultat_cts: 60_00,
  tresorerie_cts: 20_00,
  tva_a_payer_cts: 0,
  nb_transactions: 1,
  nb_a_trancher: 1,
  statut_invitation: "actif",
  mode_acces_bancaire: "gestionnaire",
  peut_connecter_sa_banque: false,
  cloture_faite: false,
  greffe_inpi_signe: false,
  guide_greffe: { depose: false, lien: "", lignes: [], pieces: [] },
  declaration_resultat: "2065",
  depot_greffe: true,
  alerte_regime: null,
  regimes_a_venir: [],
  alerte_tva: null,
  paie_par_bulletin: false,
  forme_juridique: "EURL",
  regime_libelle: "Impôt sur les sociétés",
};

type Operation = {
  ecriture_id: string;
  date: string;
  libelle: string;
  montant_cts: number;
  compte: string;
  statut: "validé" | "à trancher";
  a_justificatif: boolean;
  proposition: string | null;
  origine_proposition: "appris" | "regle" | "modele" | null;
  confiance_proposition: number | null;
  categorie?: string | null;
};

function operation(champs: Partial<Operation> & Pick<Operation, "ecriture_id" | "libelle">): Operation {
  return {
    date: "2026-06-15",
    montant_cts: -1_500,
    compte: "471",
    statut: "à trancher",
    a_justificatif: true,
    proposition: null,
    origine_proposition: null,
    confiance_proposition: null,
    ...champs,
  };
}

async function ouvrir(page: Page, operations: Operation[], decisions: { url: string }[] = []) {
  const exp = Math.floor(Date.now() / 1000) + 3600;
  await page.addInitScript(
    ([cle, valeur]) => window.localStorage.setItem(cle, valeur),
    [
      "axelcompta_session_chauffeur",
      JSON.stringify({
        accessToken: jeton({ exp, app_metadata: { dossier_id: "DEMO_sophie" } }),
        refreshToken: "rafraichissement",
        dossierId: "DEMO_sophie",
        email: "sophie@example.com",
      }),
    ] as const,
  );
  await page.route("**/*", async (route: Route) => {
    const url = route.request().url();
    const methode = route.request().method();
    if (url.includes(":3000") || url.startsWith("data:")) {
      await route.continue();
      return;
    }
    if (methode === "OPTIONS") {
      await route.fulfill({
        status: 204,
        headers: {
          "access-control-allow-origin": "*",
          "access-control-allow-headers": "*",
          "access-control-allow-methods": "*",
        },
      });
      return;
    }
    if (url.endsWith("/dossiers/DEMO_sophie") && methode === "GET") {
      await route.fulfill({ json: DOSSIER });
      return;
    }
    if (url.endsWith("/transactions") && methode === "GET") {
      await route.fulfill({ json: operations });
      return;
    }
    if (url.endsWith("/decision") && methode === "POST") {
      decisions.push({ url });
      const id = url.split("/transactions/")[1]?.split("/")[0] ?? "";
      const connue = operations.find((ligne) => ligne.ecriture_id === id);
      await route.fulfill({
        json: { ...(connue ?? operations[0]), statut: "validé", categorie: "usage_personnel" },
      });
      return;
    }
    if (url.endsWith("/correction") && methode === "POST") {
      decisions.push({ url });
      const id = url.split("/transactions/")[1]?.split("/")[0] ?? "";
      const connue = operations.find((ligne) => ligne.ecriture_id === id);
      const corps = route.request().postDataJSON() as { categorie: string };
      await route.fulfill({
        json: { ...(connue ?? operations[0]), statut: "validé", categorie: corps.categorie },
      });
      return;
    }
    await route.fulfill({ json: [] });
  });
  await page.goto("/chauffeur/DEMO_sophie");
  await expect(page.getByRole("heading", { name: "Sophie Martin" })).toBeVisible();
}

test("un millier d'opérations n'affiche qu'une carte", async ({ page }) => {
  const operations = Array.from({ length: 1000 }, (_, index) =>
    operation({
      ecriture_id: `op-${index}`,
      libelle: `Salaire semaine ${index}`,
      date: `2026-06-${String((index % 28) + 1).padStart(2, "0")}`,
    }),
  );
  await ouvrir(page, operations);

  await expect(page.getByText("1 sur 1000")).toBeVisible();
  const position = await page.getByText("1 sur 1000").evaluate((element) => {
    const parent = element.parentElement;
    return parent ? getComputedStyle(parent).position : "";
  });
  expect(position).toBe("sticky");
  await expect(page.getByRole("button", { name: "À traiter · 1000" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Personnelle" })).toHaveCount(1);
  await expect(page.getByRole("button", { name: "Ma rémunération" })).toHaveCount(1);
  const hauteur = await page.evaluate(() => document.documentElement.scrollHeight);
  expect(hauteur).toBeLessThan(8_000);
  await page.setViewportSize({ width: 375, height: 520 });
  await page.evaluate(() => window.scrollTo(0, 320));
  const compteur = await page.getByText("1 sur 1000").boundingBox();
  expect(compteur).not.toBeNull();
  expect(compteur!.y).toBeGreaterThan(48);
  expect(compteur!.y).toBeLessThan(140);
});

test("une décision se reprend avec Annuler, sans appel", async ({ page }) => {
  const decisions: { url: string }[] = [];
  await ouvrir(
    page,
    [
      operation({ ecriture_id: "a", libelle: "ZARA", date: "2026-06-20" }),
      operation({ ecriture_id: "b", libelle: "TOTAL", date: "2026-06-10" }),
    ],
    decisions,
  );

  await page.getByRole("button", { name: "Personnelle" }).click();
  await expect(page.getByText("2 sur 2")).toBeVisible();
  await expect(page.getByText("TOTAL", { exact: true })).toBeVisible();
  await expect(page.getByText("Classé en « dépense personnelle ».")).toBeVisible();
  await expect(page.getByText("« ZARA » classée en « dépense personnelle ».")).toHaveCount(1);
  await expect(page.getByRole("region", { name: "À traiter" })).toBeFocused();
  await page.getByRole("button", { name: "Annuler" }).click();

  await expect(page.getByText("1 sur 2")).toBeVisible();
  await expect(page.getByText("ZARA", { exact: true })).toBeVisible();
  await expect(page.getByText("Décision annulée.")).toHaveCount(1);
  await page.waitForTimeout(6_500);
  expect(decisions.filter((appel) => appel.url.endsWith("/decision"))).toHaveLength(0);
});

test("la décision part une fois le délai écoulé", async ({ page }) => {
  const decisions: { url: string }[] = [];
  await ouvrir(page, [operation({ ecriture_id: "a", libelle: "ZARA" })], decisions);

  await page.getByRole("button", { name: "Personnelle" }).click();
  await expect(page.getByText("Tout est à jour.")).toBeVisible();
  await expect.poll(() => decisions.length, { timeout: 8_000 }).toBe(1);
  expect(decisions[0]?.url.endsWith("/decision")).toBe(true);
});

test("le raccourci O ignore la répétition et ne s'affiche pas au tactile", async ({ page }) => {
  await page.addInitScript(() => {
    const original = window.matchMedia.bind(window);
    window.matchMedia = (query: string) => {
      if (query.includes("pointer") || query.includes("hover")) {
        return {
          matches: false,
          media: query,
          onchange: null,
          addListener() {},
          removeListener() {},
          addEventListener() {},
          removeEventListener() {},
          dispatchEvent() {
            return false;
          },
        };
      }
      return original(query);
    };
  });
  await ouvrir(page, [
    operation({
      ecriture_id: "a",
      libelle: "TOTAL",
      proposition: "carburant",
      origine_proposition: "regle",
      confiance_proposition: 0.9,
    }),
  ]);

  await expect(page.getByRole("button", { name: "Oui, c'est ça" })).toBeVisible();
  await expect(page.locator("kbd")).toHaveCount(0);
});

test("O confirme seulement la carte visible, pas une touche maintenue", async ({ page }) => {
  await ouvrir(page, [
    operation({
      ecriture_id: "a",
      libelle: "TOTAL",
      date: "2026-06-20",
      proposition: "carburant",
      origine_proposition: "regle",
      confiance_proposition: 0.9,
    }),
    operation({ ecriture_id: "b", libelle: "ZARA", date: "2026-06-10" }),
  ]);

  await expect(page.locator("kbd", { hasText: "O" })).toBeVisible();
  await page.evaluate(() => {
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "o", repeat: true, bubbles: true }));
  });
  await expect(page.getByText("1 sur 2")).toBeVisible();
  await expect(page.getByText("TOTAL")).toBeVisible();

  await page.evaluate(() => {
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "o", repeat: false, bubbles: true }));
  });
  await expect(page.getByText("2 sur 2")).toBeVisible();
  await expect(page.getByText("ZARA", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Personnelle" })).toHaveCount(1);
});

test("les opérations semblables restent un seul lot", async ({ page }) => {
  await ouvrir(page, [
    operation({
      ecriture_id: "a",
      libelle: "Salaire A",
      date: "2026-06-20",
      proposition: "salaires_personnel",
      origine_proposition: "appris",
      confiance_proposition: 1,
    }),
    operation({
      ecriture_id: "b",
      libelle: "Salaire B",
      date: "2026-06-10",
      proposition: "salaires_personnel",
      origine_proposition: "appris",
      confiance_proposition: 1,
    }),
  ]);

  await expect(page.getByRole("button", { name: "Personnelle" })).toHaveCount(1);
  await expect(page.getByRole("button", { name: "Tout classer en « Salaire d'un salarié »" })).toBeVisible();
  await expect(page.getByText("Salaire B", { exact: true })).toHaveCount(0);
});

test("une dépense sans ticket n'apparaît pas deux fois", async ({ page }) => {
  await ouvrir(page, [
    operation({
      ecriture_id: "question",
      libelle: "CAFE",
      a_justificatif: false,
      date: "2026-06-20",
    }),
    operation({
      ecriture_id: "ticket",
      libelle: "TOTAL (usage_personnel_suspect)",
      statut: "validé",
      a_justificatif: false,
      montant_cts: -800,
      date: "2026-06-12",
    }),
  ]);

  await expect(page.getByText("1 sur 2")).toBeVisible();
  await expect(page.getByText("CAFE")).toHaveCount(1);
  await expect(page.getByRole("button", { name: "Ajouter un ticket" })).toHaveCount(1);
  await expect(page.getByRole("button", { name: "Tickets · 1" })).toBeVisible();
  await expect(page.getByText("TOTAL (usage_personnel_suspect)")).toHaveCount(0);
  await expect(page.getByText("Ajouter le ticket de")).toHaveCount(0);
});

test("une opération se corrige depuis Mouvements et s'annule", async ({ page }) => {
  const decisions: { url: string }[] = [];
  await ouvrir(
    page,
    [
      operation({
        ecriture_id: "frais",
        libelle: "FRAIS BANQUE",
        statut: "validé",
        compte: "627",
        categorie: "frais_bancaires",
        a_justificatif: true,
      }),
    ],
    decisions,
  );

  await page.getByRole("button", { name: "Mouvements" }).click();
  await page.getByRole("button", { name: "Corriger FRAIS BANQUE" }).click();
  await page.getByRole("button", { name: "Personnelle" }).click();
  await expect.poll(() => decisions.some((appel) => appel.url.endsWith("/correction"))).toBe(true);

  await page.getByRole("button", { name: "Annuler" }).click();
  await expect.poll(() => decisions.filter((appel) => appel.url.endsWith("/correction"))).toHaveLength(2);
  await expect(page.getByText("Décision annulée.")).toHaveCount(1);
});
