# Activity Accounts submission boundary

The Contact Us, Find Peace in Christ, and Prayer Request forms are local previews. Each form uses `data-integration` to name its future Activity Accounts integration point and `data-submission-state="not-connected"` to make the current state explicit. Required email and message fields use native browser validation. The site JavaScript prevents network submission and displays a clear status after a valid local preview; no request is sent and no recipient or credential is embedded in this repository.

When the separately authorized Activity Accounts submission service is ready, its owner can connect these form identifiers to an approved endpoint, recipient, consent and privacy rules, retention policy, and server-side abuse controls. Do not place credentials or private routing details in this static site. Until then, keep these forms non-submitting and do not test with real prayer requests or production form endpoints.

PRCC remains an independent static site. This boundary does not change Activity Accounts or grant the site access to its production systems.
