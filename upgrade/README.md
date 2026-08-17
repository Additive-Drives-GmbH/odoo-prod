## Description:

Technical, dependency-free carrier module for this repository's 18.0 -> 19.0
upgrade project.

It only depends on `base` and is `auto_install`, so it is guaranteed to be
installed - and installed early, before any other custom module - in every
database as soon as the module list is updated. It carries no models or
views of its own; its only purpose is to host the cross-module upgrade
scripts (see `migrations/`) needed for the 19.0 migration:

- Module operations (remove, rename, merge, ...) which the Odoo upgrade-util
  documentation recommends running from a "base" module rather than from the
  migrations folder of one of the affected feature modules.
- Force-installing new custom modules that only become installable once the
  server is running 19.0 (e.g. modules depending on `html_editor`), via
  `util.force_install_module`, since they cannot be listed as a regular
  `depends` of this module without breaking its own installability on 18.0.

This module must already be installed on the source (18.0) database before
the Odoo.sh version upgrade is requested - a fresh install only registers
the module, it does not by itself trigger any migration script. Once the
19.0 branch's code (with this module's version bumped to match the
`migrations/` folder below) is deployed against the upgraded database, the
version change from `18.0.1.0.0` to `19.0.1.0.0` is what causes
`migrations/19.0.1.0.0/pre-migrate.py` to run.

## Configure:

Addon needs no configuration.

## History:

- 1.0.0: Initial version. Adds the `migrations/19.0.1.0.0/pre-migrate.py`
  script that, as part of the Odoo 18.0 -> 19.0 upgrade:
  - removes `ife_textblock` and its dependent modules.
  - force-installs `manatec_html_editor_pagebreak`.

## Maintainer:

This module is maintained by IFE Gmbh.
