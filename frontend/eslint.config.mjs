// Config plate (ESLint 9+) : `next lint` et le format `.eslintrc.json`
// n'existent plus depuis Next 16 (migration doc DESIGN.md/doc 18,
// 2026-09-22) — équivalent exact de l'ancien
// `{ "extends": "next/core-web-vitals" }`.
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";

const config = [...nextCoreWebVitals, { ignores: [".next/**", "e2e/**"] }];

export default config;
