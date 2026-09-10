# Third-party notices

The root MIT license covers original Den project code. Third-party software,
fonts, and bundled notices retain their respective licenses.

## Bundled assets and service wrapper

| Component | Version or snapshot | License and notice | Upstream |
| --- | --- | --- | --- |
| Bootstrap CSS | 4.6.2 | [MIT](infonet/myapp/static/vendor/bootstrap-LICENSE.txt) | [Bootstrap](https://github.com/twbs/bootstrap) |
| Nunito fonts | Bundled Google Fonts snapshot | [SIL Open Font License 1.1](infonet/myapp/static/vendor/nunito-OFL.txt) | [Nunito](https://github.com/google/fonts/tree/main/ofl/nunito) |
| WinSW executable | 2.12.0 | [MIT](deploy/vendor/WinSW-LICENSE.txt) | [WinSW](https://github.com/winsw/winsw/tree/v2.12.0) |

Source URLs and SHA-256 hashes for bundled vendor artifacts are recorded in
`deploy/vendor-manifest.json`. Preserve notices when redistributing these files.
Bootstrap JavaScript and jQuery are not part of Den's browser bundle.

## Python runtime dependencies

Versions match `infonet/requirements.txt`. License files below were copied from
the installed distributions matching that lock file. Packages are installed by
pip; environments and cached wheels are not committed to the source repository.

| Dependency | Version | License | Notice |
| --- | --- | --- | --- |
| anyio | 4.15.1 | MIT | [License](docs/third-party/anyio/licenses/LICENSE) |
| asgiref | 3.12.1 | BSD-3-Clause | [License](docs/third-party/asgiref/licenses/LICENSE) |
| certifi | 2026.7.22 | MPL-2.0 | [License](docs/third-party/certifi/licenses/LICENSE) |
| django | 6.0.8 | BSD-3-Clause | [License](docs/third-party/django/licenses/LICENSE) |
| h11 | 0.16.0 | MIT | [License](docs/third-party/h11/licenses/LICENSE.txt) |
| httpcore | 1.0.9 | BSD-3-Clause | [License](docs/third-party/httpcore/licenses/LICENSE.md) |
| httpx | 0.28.1 | BSD-3-Clause | [License](docs/third-party/httpx/licenses/LICENSE.md) |
| idna | 3.19 | BSD-3-Clause | [License](docs/third-party/idna/licenses/LICENSE.md) |
| sqlparse | 0.6.0 | BSD-3-Clause | [License](docs/third-party/sqlparse/licenses/LICENSE) |
| typing-extensions | 4.16.0 | PSF-2.0 | [License](docs/third-party/typing-extensions/licenses/LICENSE) |
| tzdata | 2026.3 | Apache-2.0 | [License](docs/third-party/tzdata/licenses/LICENSE) |
| waitress | 3.0.2 | ZPL-2.1 | [License](docs/third-party/waitress/LICENSE.txt) |
| whitenoise | 6.12.0 | MIT | [License](docs/third-party/whitenoise/licenses/LICENSE) |

Additional license material shipped by Django and tzdata is preserved under
`docs/third-party/`. Python itself is distributed separately under the PSF license.
The optional Tailscale client and OpenRouter service are separately installed or
accessed; their own terms apply and they are not relicensed by this repository.

When updating dependencies or vendor assets, refresh this inventory and the
corresponding notices alongside lock-file hashes. Do not imply that the root MIT
license replaces a dependency's license.
