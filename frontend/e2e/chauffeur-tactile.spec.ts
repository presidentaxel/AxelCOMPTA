import { expect, test, type Page, type Route, devices } from "@playwright/test";

import { clavierOuvert, insetClavier } from "../lib/clavier-viewport";

const iphone = devices["iPhone 13"];
test.use({
  viewport: iphone.viewport,
  userAgent: iphone.userAgent,
  isMobile: iphone.isMobile,
  hasTouch: iphone.hasTouch,
  deviceScaleFactor: iphone.deviceScaleFactor,
});

function jeton(claims: Record<string, unknown>): string {
  const coder = (valeur: object) => Buffer.from(JSON.stringify(valeur)).toString("base64");
  return `${coder({ alg: "none", typ: "JWT" })}.${coder(claims)}.signature`;
}

const DOSSIER = {
  dossier_id: "DEMO_sophie",
  nom: "Sophie Martin",
  tva_recettes_regime: "franchise",
  plateformes: [],
  exercice_debut: "2025-01-01",
  exercice_fin: "2025-12-31",
  ca_ht_cts: 100_00,
  charges_cts: 40_00,
  resultat_cts: 60_00,
  tresorerie_cts: 20_00,
  tva_a_payer_cts: 0,
  nb_transactions: 2,
  // Activité garde une ligne à classer. L'exercice, lui, est clos : la liasse
  // s'ouvre, ce que la PR 76 interdit tant qu'il reste une opération.
  nb_a_trancher: 0,
  statut_invitation: "actif",
  mode_acces_bancaire: "gestionnaire",
  peut_connecter_sa_banque: false,
  cloture_faite: true,
  greffe_inpi_signe: false,
  guide_greffe: {
    depose: true,
    lien: "https://example.test/inpi",
    lignes: [],
    pieces: [{ nom: "Statuts", detail: "PDF", document: "statuts.pdf" }],
  },
  declaration_resultat: "2065",
  depot_greffe: true,
  alerte_regime: null,
  regimes_a_venir: [],
  alerte_tva: null,
  paie_par_bulletin: true,
  forme_juridique: "EURL",
  regime_libelle: "Impôt sur les sociétés",
};

const A_TRANCHER = {
  ecriture_id: "zara-1",
  date: "2025-06-01",
  libelle: "ZARA",
  montant_cts: -4_200,
  compte: "471",
  statut: "à trancher",
  a_justificatif: true,
  proposition: null,
  origine_proposition: null,
  confiance_proposition: null,
};

const SANS_TICKET = {
  ecriture_id: "total-1",
  date: "2025-06-02",
  libelle: "TOTAL (carburant)",
  montant_cts: -5_000,
  compte: "606",
  statut: "validé",
  a_justificatif: false,
  proposition: "carburant",
  origine_proposition: "regle",
  confiance_proposition: null,
};

function contraste(premier: string, second: string): number {
  const rapport = (couleur: string) => {
    const valeurs = couleur.match(/\d+(\.\d+)?/g)?.slice(0, 3).map(Number) ?? [0, 0, 0];
    const lineaire = valeurs.map((canal) => {
      const c = canal / 255;
      return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * lineaire[0]! + 0.7152 * lineaire[1]! + 0.0722 * lineaire[2]!;
  };
  const [haut, bas] = [rapport(premier), rapport(second)].sort((a, b) => b - a);
  return (haut! + 0.05) / (bas! + 0.05);
}

async function masquerIndicateurDev(page: Page) {
  await page.evaluate(() => {
    document.querySelectorAll("nextjs-portal").forEach((noeud) => noeud.remove());
  });
}

async function hauteur(page: Page, locator: ReturnType<Page["locator"]>): Promise<number> {
  const boite = await locator.boundingBox();
  expect(boite).not.toBeNull();
  return boite!.height;
}

async function taillePolice(locator: ReturnType<Page["locator"]>): Promise<number> {
  const taille = await locator.evaluate((element) => getComputedStyle(element).fontSize);
  return Number.parseFloat(taille);
}

async function bouchon(route: Route) {
  const url = route.request().url();
  const methode = route.request().method();
  if (url.endsWith("/dossiers/DEMO_sophie") && methode === "GET") {
    await route.fulfill({ json: DOSSIER });
    return;
  }
  if (url.endsWith("/transactions") && methode === "GET") {
    await route.fulfill({ json: [A_TRANCHER, SANS_TICKET] });
    return;
  }
  if (url.includes("/cloture-exercice") && methode === "GET") {
    await route.fulfill({
      json: {
        possible: true,
        raison: null,
        exercice_debut: "2025-01-01",
        exercice_fin: "2025-12-31",
        nouvel_exercice_debut: "2026-01-01",
        ecritures: ["Liquidation de la TVA de l'exercice"],
        changements: [],
        attestation: "J'atteste la clôture.",
      },
    });
    return;
  }
  if (url.includes("/provisions-cloture") && methode === "GET") {
    await route.fulfill({ json: { lignes: [] } });
    return;
  }
  if (url.includes("/affectation")) {
    await route.fulfill({ json: { applicable: false, raison: "Rien à affecter." } });
    return;
  }
  if (url.includes("/dividendes")) {
    await route.fulfill({
      json: {
        applicable: true,
        raison: null,
        annee_exercice: 2025,
        brut_cts: 10_000,
        declare: false,
        verse_le: null,
        dispense_prelevement: false,
        prelevement_forfaitaire_cts: 1_280,
        csg_cts: 900,
        crds_cts: 50,
        solidarite_cts: 400,
        total_retenu_cts: 2_630,
        net_a_virer_cts: 7_370,
        echeance_2777: "2026-01-15",
      },
    });
    return;
  }
  await route.fulfill({ json: [] });
}

async function session(page: Page) {
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
  await page.route("**/*", async (route) => {
    const url = route.request().url();
    if (url.includes(":3000") || url.startsWith("data:")) {
      await route.continue();
      return;
    }
    if (route.request().method() === "OPTIONS") {
      await route.fulfill({ status: 204 });
      return;
    }
    await bouchon(route);
  });
}

test("l'inset clavier ignore un innerHeight qui rétrécit avec lui", () => {
  expect(insetClavier(844, 844, 0)).toBe(0);
  expect(clavierOuvert(0)).toBe(false);
  expect(clavierOuvert(80)).toBe(false);
  expect(insetClavier(844, 490, 0)).toBe(354);
  expect(clavierOuvert(354)).toBe(true);
});

test("la connexion chauffeur tient dans la cible tactile", async ({ page }) => {
  await page.goto("/chauffeur/login");
  const viewport = await page.locator('meta[name="viewport"]').getAttribute("content");
  expect(viewport).toContain("width=device-width");
  expect(viewport).toContain("initial-scale=1");
  expect(viewport).toContain("viewport-fit=cover");
  expect(viewport).not.toContain("maximum-scale");

  const email = page.getByPlaceholder("Votre e-mail");
  expect(await taillePolice(email)).toBeGreaterThanOrEqual(16);
  expect(await hauteur(page, email)).toBeGreaterThanOrEqual(44);
  const placeholder = await email.evaluate((element) => getComputedStyle(element, "::placeholder").color);
  const fond = await email.evaluate((element) => getComputedStyle(element).backgroundColor);
  expect(contraste(placeholder, fond)).toBeGreaterThanOrEqual(4.5);

  expect(await hauteur(page, page.getByRole("button", { name: "Se connecter" }))).toBeGreaterThanOrEqual(44);
  expect(await hauteur(page, page.getByRole("button", { name: "Mot de passe oublié" }))).toBeGreaterThanOrEqual(44);
  expect(await taillePolice(page.getByText("Alpha"))).toBeGreaterThanOrEqual(12);

  const coque = page.locator(".chauffeur");
  await expect(coque).toHaveCSS("position", "fixed");
  const vvh = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--vvh").trim());
  expect(vvh.endsWith("px")).toBe(true);
  await masquerIndicateurDev(page);
  await page.screenshot({ path: "/opt/cursor/artifacts/chauffeur-login.png", fullPage: false });
});

test("le bouton gestionnaire reste à la taille du design", async ({ page }) => {
  await page.goto("/connexion");
  expect(await hauteur(page, page.getByRole("button", { name: "Se connecter" }))).toBe(36);
});

test("les contrôles du dossier chauffeur font 44 px et passent AA", async ({ page }) => {
  await session(page);
  await page.goto("/chauffeur/DEMO_sophie");
  await expect(page.getByRole("heading", { name: "Sophie Martin" })).toBeVisible();

  const activite = page.getByRole("link", { name: "Activité" });
  await expect(activite).toBeVisible();
  expect(await hauteur(page, activite)).toBeGreaterThanOrEqual(44);
  expect(await taillePolice(activite)).toBeGreaterThanOrEqual(12);
  expect(await hauteur(page, page.getByRole("button", { name: "Notifications" }))).toBeGreaterThanOrEqual(44);
  const onglet = page.getByRole("button", { name: /À traiter/ });
  await expect(onglet).toBeVisible();
  expect(await hauteur(page, onglet)).toBeGreaterThanOrEqual(44);

  const montant = page.locator(".text-amount-positive").first();
  const vert = await montant.evaluate((element) => getComputedStyle(element).color);
  const toile = await montant.evaluate((element) => getComputedStyle(element).backgroundColor);
  const fondMontant = toile === "rgba(0, 0, 0, 0)" ? "rgb(255, 255, 255)" : toile;
  expect(contraste(vert, fondMontant)).toBeGreaterThanOrEqual(4.5);

  const autre = page.getByRole("button", { name: "Autre chose" });
  await expect(autre).toBeVisible();
  await autre.click();
  const libre = page.getByPlaceholder("à quoi correspond-elle ?");
  expect(await taillePolice(libre)).toBeGreaterThanOrEqual(16);
  expect(await hauteur(page, libre)).toBeGreaterThanOrEqual(44);
  expect(await hauteur(page, page.getByRole("button", { name: "Envoyer" }))).toBeGreaterThanOrEqual(44);
  expect(
    await hauteur(page, page.getByRole("button", { name: "Mes dividendes", exact: true })),
  ).toBeGreaterThanOrEqual(44);

  await page.getByRole("button", { name: "Mouvements" }).click();
  const ticket = page.getByRole("button", { name: "Ajouter un ticket" });
  await expect(ticket).toBeVisible();
  expect(await hauteur(page, ticket)).toBeGreaterThanOrEqual(44);
  await masquerIndicateurDev(page);
  await page.screenshot({ path: "/opt/cursor/artifacts/chauffeur-activite.png", fullPage: false });

  await page.getByRole("link", { name: "Exercice" }).click();
  await expect(page.getByRole("heading", { name: "Exercice", exact: true })).toBeVisible();
  const compte = page.getByLabel("De quoi s'agit-il ?");
  await expect(compte).toBeVisible();
  expect(await taillePolice(compte)).toBeGreaterThanOrEqual(16);
  expect(await hauteur(page, compte)).toBeGreaterThanOrEqual(44);
  expect(await hauteur(page, page.getByLabel("Montant"))).toBeGreaterThanOrEqual(44);
  const paie = page.getByLabel("Salaire avant retenues");
  await expect(paie).toBeVisible();
  expect(await taillePolice(paie)).toBeGreaterThanOrEqual(16);
  expect(await hauteur(page, paie)).toBeGreaterThanOrEqual(44);

  const badge = page.getByText("À signer", { exact: true });
  await expect(badge).toBeVisible();
  const encreBadge = await badge.evaluate((element) => getComputedStyle(element).color);
  const fondBadge = await badge.evaluate((element) => getComputedStyle(element).backgroundColor);
  expect(contraste(encreBadge, fondBadge)).toBeGreaterThanOrEqual(4.5);
  expect(await taillePolice(badge)).toBeGreaterThanOrEqual(12);

  const telecharger = page.getByRole("button", { name: "Télécharger", exact: true });
  await telecharger.scrollIntoViewIfNeeded();
  expect(await hauteur(page, telecharger)).toBeGreaterThanOrEqual(44);

  await page.getByRole("button", { name: "Récupérer la liasse" }).click();
  const dialogue = page.getByRole("dialog");
  await expect(dialogue).toBeVisible();
  const maxHauteur = await dialogue.evaluate((element) => getComputedStyle(element).maxHeight);
  expect(maxHauteur).not.toBe("none");
  const boite = await dialogue.boundingBox();
  expect(boite!.height).toBeLessThanOrEqual(page.viewportSize()!.height);
  await masquerIndicateurDev(page);
  await page.screenshot({ path: "/opt/cursor/artifacts/chauffeur-dialogue.png", fullPage: false });
  await page.keyboard.press("Escape");

  await page.goto("/chauffeur/DEMO_sophie/resultat");
  const date = page.locator('input[type="date"]');
  await expect(date).toBeVisible();
  expect(await taillePolice(date)).toBeGreaterThanOrEqual(16);
  expect(await hauteur(page, date)).toBeGreaterThanOrEqual(44);

  await page.goto("/chauffeur/compte");
  const sortie = page.getByRole("button", { name: "Se déconnecter" });
  await expect(sortie).toBeVisible();
  expect(await hauteur(page, sortie)).toBeGreaterThanOrEqual(44);

  const affichage = await page.evaluate(() => {
    document.documentElement.setAttribute("data-clavier", "");
    const barre = document.querySelector("nav");
    return barre ? getComputedStyle(barre).display : "absente";
  });
  expect(affichage).toBe("none");
});
