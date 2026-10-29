# NeoToyBox Public Examples v0.18

This repository contains reusable validation code, synthetic inventory and selected configuration templates.

**This is an example library, not a production deployment repository.** All example IPs, MACs, hostnames and domain values are synthetic. No secrets, encrypted secrets, production inventory, deployment playbooks, private history or operational evidence are included.

- [Public design](00_統合設計書_v0.18.md)
- [Publishing and CI policy](docs/PUBLISHING.md)
- [Security policy](SECURITY.md)

Install requirements-ci.txt in a virtual environment and run python tools/ci_check.py. CI runs privacy/hash/allowlist, YAML/Jinja/link, inventory and nonempty unit-test validation. It does not deploy or connect to infrastructure.

Template variables require your own reviewed configuration. The sample network policy uses 10.80/10.81/10.82 exclusively. Do not replace examples with your real values in a public PR.

No software license has been selected by the owner yet. Public visibility does not itself grant an open-source license.
