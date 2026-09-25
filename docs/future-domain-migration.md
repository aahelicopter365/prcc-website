# Future custom-domain migration

This repository currently targets `https://aahelicopter365.github.io/prcc-website/`. No custom domain or DNS record is configured. Keep `prccgreensboro.org` and its existing GoDaddy site untouched until PRCC approves a separate migration and the new site is verified.

## Preparation after domain approval

1. Confirm the exact domain and its owner. Verify the domain with GitHub before adding it to Pages to reduce domain-takeover risk.
2. Confirm the GitHub Pages site is publishing successfully over HTTPS at its `github.io` URL.
3. Add the approved hostname in the repository's Pages settings before changing DNS.
4. For an apex hostname, configure the DNS provider with GitHub Pages `A` records: `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, and `185.199.111.153`. Optional IPv6 `AAAA` records are `2606:50c0:8000::153`, `2606:50c0:8001::153`, `2606:50c0:8002::153`, and `2606:50c0:8003::153`.
5. For a subdomain, create a `CNAME` to `aahelicopter365.github.io` (without the repository name). Do not use wildcard DNS. If both apex and `www` are approved, configure each record and confirm GitHub's redirect behavior.
6. Wait for DNS propagation, verify records with `Resolve-DnsName`, then wait for GitHub's certificate provisioning and enable Enforce HTTPS when available.
7. Verify homepage, styles, images, navigation, nested pages, forms, mixed-content absence, and mobile layouts on the custom hostname. Keep the existing GoDaddy website available until PRCC signs off on the replacement.

## Rollback

If verification fails, remove the custom hostname from GitHub Pages and restore the prior DNS values from the DNS provider's recorded pre-change snapshot. Keep the existing GoDaddy site and domain configuration available until rollback verification succeeds. Do not delete the prior hosting setup during the cutover.

GitHub's current instructions: [Managing a custom domain for GitHub Pages](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site) and [Securing your GitHub Pages site with HTTPS](https://docs.github.com/en/pages/getting-started-with-github-pages/securing-your-github-pages-site-with-https).
