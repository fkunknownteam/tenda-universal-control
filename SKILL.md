---
name: tenda-universal-control
description: Use when controlling Tenda models through one API.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [networking, router, tenda, universal, cli]
---

# Universal Tenda router control

## When to Use

Use when an app needs one stable interface across different Tenda models and
firmware generations. The skill discovers the router, selects an adapter and
normalizes every response.

## Layout

```
scripts/tenda_cli.py   CLI / app-facing entry point
core/                  client, capabilities, response normalization
discovery/             vendor, model, firmware and API-family detection
auth/                  auth strategy selection and session handling
adapters/              per-family adapters + factory
tests/                 mock-based tests
examples/              app integration example
```

## Use from Hermes

```sh
export TENDA_HOST=192.168.0.1
export TENDA_PASSWORD='local-admin-password'
S=~/.hermes/skills/networking/tenda-universal-control
python3 $S/scripts/tenda_cli.py diagnose
python3 $S/scripts/tenda_cli.py capabilities --json
python3 $S/scripts/tenda_cli.py status --json
python3 $S/scripts/tenda_cli.py clients --json
python3 $S/scripts/tenda_cli.py wifi get --json
python3 $S/scripts/tenda_cli.py reboot --yes --json
python3 $S/scripts/tenda_cli.py --simulate aes_goahead status --json
```

Every command returns the same envelope:

```json
{"success":true,"router":{"vendor":"Tenda","model":"...","firmware":"..."},
 "action":"status","data":{},"error":null}
```

Unsupported features return `success:false`, `error.kind:"unsupported"` and
the requested `feature` — never a fabricated success.

## Safety

- Read commands are the default. `reboot`, `reset`, Wi-Fi/WAN/LAN changes,
  block and bandwidth limits require `--yes`.
- Before a risky config change the client calls the router's backup endpoint
  when that capability exists.
- Discovery uses only safe read requests. Unknown models get an
  `unknown` adapter with almost no capabilities, plus a discovery report.
- Credentials come from `TENDA_HOST` / `TENDA_PASSWORD` / `TENDA_USERNAME`
  or the app's secure storage. Passwords, tokens, cookies and AES signs are
  never printed.

## Testing status

All current tests use mocked/stub router responses. No router model is claimed
hardware-verified by this universal layer. Earlier hardware verification of a
single AC10 belongs to the separate `routerctl-ac10` project.
