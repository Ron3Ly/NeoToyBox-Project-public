# NeoToyBox Public Examples v0.18

This repository contains reusable validation code, synthetic inventory and selected configuration templates.

**This is an example library, not a production deployment repository.** All example IPs, MACs, hostnames and domain values are synthetic. No secrets, encrypted secrets, production inventory, deployment playbooks, private history or operational evidence are included.

- [Public design](00_統合設計書_v0.18.md)
- [Publishing and CI policy](docs/PUBLISHING.md)
- [Security policy](SECURITY.md)

Install requirements-ci.txt in a virtual environment and run python tools/ci_check.py. CI runs privacy/hash/allowlist, YAML/Jinja/link, inventory and nonempty unit-test validation. It does not deploy or connect to infrastructure.

Validate changes on a dedicated dev host before promoting the same revision to prod. Dev and prod use the synthetic 10.82 and 10.80 network families respectively. Nextcloud uses its built-in preview providers.

Template variables require your own reviewed configuration. Keep physical host specifications and site-specific configuration in the private deployment inventory.

No software license has been selected by the owner yet. Public visibility does not itself grant an open-source license.
