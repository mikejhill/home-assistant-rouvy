# Releasing

Releases are cut from `main` by the **Release** workflow. HACS offers each
GitHub release to users as an update.

## Steps

1. Make sure everything to ship is merged into `main` and CI is green.
2. Check that `CHANGELOG.md` has notes under `## [Unreleased]`. The workflow
   refuses to release with an empty section.
3. Pick the version ([Semantic Versioning](https://semver.org/)): breaking
   changes to entities or actions bump the major version, new features bump
   the minor version, and fixes bump the patch version.
4. Run **Actions → Release → Run workflow** on `main` with that version
   (for example `2.1.0`, without a `v`).

The workflow then:

1. runs `scripts/release.py prepare <version>`, which sets the version in
   `pyproject.toml`, `src/rouvy_api/_version.py`, and
   `custom_components/rouvy/manifest.json`, and moves the `[Unreleased]` notes
   under a dated `## [<version>]` heading;
2. refreshes `uv.lock` and re-vendors the library into the integration;
3. runs every quality gate (`poe check`);
4. builds the wheel, sdist, and `rouvy.zip` (the integration folder);
5. commits `chore(release): v<version>`, tags `v<version>`, pushes both, and
   publishes a GitHub release whose notes are that CHANGELOG section.

## Branch protection

The **Require CI on main** ruleset only accepts commits on `main` whose
`ci-pass` check succeeded, and blocks force-pushes and deletion. Changes land
through pull requests. The Release workflow pushes its version-bump commit
directly; it authenticates with the write deploy key stored in the
`RELEASE_DEPLOY_KEY` secret, which is the ruleset's only bypass actor. To
rotate it, add a new write deploy key, update the secret, and delete the old
key.

## Preview locally

```bash
uv run scripts/release.py prepare 2.1.0
```

```bash
git diff
```

```bash
git checkout -- .
```

## After a release

- Live smoke tests (`poe live`) and the contract canary run on their own
  schedules; run them by hand after a release if Rouvy changed recently.
- In Home Assistant, HACS shows the update on the Rouvy integration. Restart
  Home Assistant after updating.
