# Activity Accounts integration boundary

PRCC is maintained as an independent, plain HTML/CSS repository so its build and failures cannot affect Activity Accounts or another project. The site uses repository-relative navigation and has no server, database, paid hosting dependency, or shared infrastructure changes.

The available execution environment did not expose a PRCC/Rocky project root or an authorized Rocky Linux connection. The existing ADR GitHub event path is configured for the separate Contract Radar workflow and does not grant repository content write permission. No unrelated SSH host, website server, or Activity Accounts production component was used. This clone therefore remains standalone until an authorized PRCC project/host mapping is available.

The GitHub Pages workflow is prepared in `.github/workflows/pages.yml`. It can publish the repository root after the repository owner grants the required GitHub write and Pages workflow access. No public push or deployment has occurred.
