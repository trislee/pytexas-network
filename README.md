# PyTexas talk entity network

Interactive graph of named entities extracted from PyTexas conference talk transcripts (2017–present). Built with [Vite](https://vitejs.dev/), React, and [react-sigma](https://sim51.github.io/react-sigma/).

## Scripts

| Command | Description |
|--------|-------------|
| `npm start` | Dev server ([vite.config.mts](vite.config.mts) port, default 3000). |
| `npm run build` | Production bundle in `build/`. |
| `npm run preview` | Serve the production build locally. |

Graph JSON for the app lives at `public/pytexas.json` (generate via your pipeline, or the GitHub Action copies `public/dataset.json` as a fallback when `pytexas.json` is absent).

## GitHub Pages

Deploy uses [.github/workflows/deploy-pages.yml](.github/workflows/deploy-pages.yml). In the repo **Settings → Pages**, set the source to **GitHub Actions**.
