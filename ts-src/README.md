# TypeScript Orchestration Layer

This directory provides a thin TypeScript CLI wrapper around the **Python acquisition engine**.

- **Python is the primary engine.** All heavy lifting (scraping, LLM calls, PDF generation) lives in `src/` (Python).
- This TypeScript layer is useful for teams that prefer a Node.js entry point or want to integrate the pipeline into a TS/JS monorepo.

## Usage

```bash
cd ts-src
npm install
npm run start -- run --region "Cyberjaya" --keywords cafe restaurant
```

The TS CLI simply spawns the Python backend as a subprocess.
