# Contributing to TeacherOS

Thank you for helping improve TeacherOS.

## Before contributing

- Use Python 3.12 and the pinned `requirements.txt`.
- Install web dependencies from `web/package-lock.json`.
- Keep credentials in ignored local files only.
- Never commit curriculum PDFs, trade books, pasted curriculum, generated
  lesson packages, Google document identifiers, tokens, databases, or output
  artifacts.
- Use original synthetic fixtures for tests.
- Do not paste student information or private teacher data into issues or
  pull requests.

## Development checks

Run the complete Python tests, web tests, production web build, Python
compilation, `git diff --check`, dependency audits, and secret scans before
opening a pull request.

Automated tests must use deterministic fake providers. They must not call live
AI services, Google APIs, OAuth flows, or paid external services.

## Curriculum changes

Curriculum adapters may store non-expressive metadata such as identifiers,
page coordinates, checksums, and source availability. Do not commit source
passages or answer keys. Any retained licensed curriculum configuration must
include the required attribution and remain separate from original software.

By contributing original software, you agree that it may be distributed under
AGPL-3.0-only. Do not submit code or content you are not authorized to
distribute.
