# Security Policy

## Supported versions

TeacherOS is under active development. Security fixes are applied to the
current `main` branch.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability or exposed
credential. Use GitHub's private vulnerability reporting feature for this
repository. Include the affected component, reproduction steps, likely
impact, and any suggested mitigation. Do not include real curriculum,
student information, API keys, OAuth tokens, or other sensitive data.

If private vulnerability reporting is unavailable, contact the repository
owner through their GitHub profile and request a private reporting channel.

## Local security model

TeacherOS is a local application. Its Python API binds only to
`127.0.0.1`, accepts browser requests only from the documented local
frontend origins, and requires an ephemeral per-process session token for
state-changing requests. It is not designed to be exposed directly to a
network or the public internet.

API keys and Google OAuth files must remain on the user's computer. Never
attach `.env`, `credentials*.json`, `token*.json`, local databases,
curriculum files, generated lesson packages, or `output/` contents to an
issue.

## Credential response

If a credential is accidentally disclosed:

1. Revoke or rotate it with the issuing provider.
2. Remove it from the current tree.
3. Purge it from Git history before publishing rewritten refs.
4. Re-run the repository and history secret scans.
