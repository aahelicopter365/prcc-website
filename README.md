# Pleasant Ridge Christian Church

Independent static reconstruction for GitHub Pages at `/prcc-website/`.

## Local development and verification

Run `python -m http.server 8000` from this directory and open `http://localhost:8000/`. Run `python tools/verify_site.py` to check the captured pages, local links, assets, required manifest fields, and repository-path safety.

## Content and assets

`content/source-manifest.json` keeps source URLs, navigation labels, destination routes, status fields, forms, and image provenance separate from the presentation templates. `python tools/migrate_source.py` refreshes the manifest, pages, and public images from the PRCC site with a maximum of 80 pages, a 2 MB page limit, and a 25 MB total image limit. The source navigation and sitemap currently list the same 16 pages. Generated HTML is refreshed from the public source; update the generator when a deliberate presentation or content correction must survive a refresh. No GoDaddy platform code is used.

## Forms

Contact, prayer, and “Find Peace in Christ” controls are presentational and cannot submit data. A church-approved recipient and submission service are required before enabling them.

## Deployment

`.github/workflows/pages.yml` publishes the repository root to GitHub Pages after a commit reaches `main` or a manual workflow dispatch. Repository write and Pages workflow access are required. No custom domain is configured, and the existing PRCC production website and DNS remain untouched. See `docs/future-domain-migration.md` for the separately approved future migration procedure.

## Visual mirror

`python tools/render_visual_mirror.py` renders the 15 non-home routes from the captured content and repository-local image inventory. `index.html` and `home.css` contain the individually matched home composition. The production image inventory keeps public source URLs, while `content/production-assets.json` records local asset paths and SHA-256 hashes. Contact and prayer previews contain no active submit action.
