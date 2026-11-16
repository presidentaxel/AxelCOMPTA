/** @type {import('next').NextConfig} */
const nextConfig = {
  // Next 16 régénère sinon AGENTS.md/CLAUDE.md (boilerplate générique) à
  // chaque `next dev` — le projet a déjà sa propre documentation (docs/,
  // DESIGN.md), pas besoin d'un doublon générique non versionné.
  agentRules: false,
  // Image autonome pour le droplet (frontend/Dockerfile). Le logo est un
  // petit PNG statique : pas de sharp dans l'image de production.
  output: "standalone",
  images: { unoptimized: true },
};

export default nextConfig;
