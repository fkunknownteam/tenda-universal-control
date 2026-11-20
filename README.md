# Universal Tenda control skill

One stable API for multiple Tenda firmware families. The app talks only to
`TendaUniversal`; the skill handles discovery, authentication, adapter choice
and response normalization.

## Flow

```
App → TendaUniversal → Discovery → Auth → Adapter → Router
                     ← normalized envelope ←
```

## Use

```sh
export TENDA_HOST=192.168.0.1
export TENDA_PASSWORD='local-admin-password'
S=~/.hermes/skills/networking/tenda-universal-control
python3 $S/scripts/tenda_cli.py diagnose
python3 $S/scripts/tenda_cli.py capabilities
python3 $S/scripts/tenda_cli.py status
python3 $S/scripts/tenda_cli.py clients list
python3 $S/scripts/tenda_cli.py wifi get
python3 $S/scripts/tenda_cli.py reboot --yes
python3 $S/scripts/tenda_cli.py --simulate legacy_ecos status
```

Never put credentials in command-line arguments. `TENDA_PASSWORD` (or the app's
secure credential store) is the only input.

## Adapter families

- `aes_goahead`: modern AC/AX/Nova, `md5(pw)` login + `/goform/stokCfg` AES sign.
- `legacy_ecos`: older eCos firmware, `getstok` + `md5(base64(pw)+token)`.
- `module_goform`: `getStatus?modules=...` style UI, base64/open login.
- `basic_http`: minimal goform getters.
- `unknown`: safe discovery only; unsupported features are reported honestly.

## Response contract

```json
{"success": true,
 "router": {"vendor": "Tenda", "model": "AC10", "firmware": "V16.03.10.10_multi",
            "api_family": "aes_goahead"},
 "action": "status", "data": {}, "error": null}
```

Unsupported feature:

```json
{"success": false,
 "error": {"kind": "unsupported", "feature": "qos",
           "message": "QoS is not available on this router/firmware."}}
```

## Safety

Read commands are safe. `reboot`, `reset`, Wi-Fi/WAN/LAN changes, block and
bandwidth limits require confirmation. Before a destructive config change the
client calls the backup endpoint when the adapter has one.

## Tests

`python3 -m unittest discover -s tests -v` — all tests use mocked router
responses. No hardware-verified claims are made by this universal layer.
