# GPG signing key for the APT repository

The APT repository is signed with a dedicated GPG key. It consists of two parts:

- a **master key** that only certifies. It stays offline and is only needed to create, extend or revoke the subkey.
- a **signing subkey** that is stored as a secret in GitHub and signs the repository metadata in CI.

Neither key has a passphrase, because CI has to sign unattended. Removing the passphrase from an exported subkey does not work (GnuPG reports "No secret key" for the stripped master key), so the key is created without one. The master key is protected by where it is stored: an encrypted disk, an encrypted USB stick or a password manager.

The commands below were run against a clean GnuPG keyring together with `scripts/publish-apt.sh`, which produced a valid signed repository.

## 1. Create the key

```bash
gpg --quick-generate-key "PiCompose Archive <picompose@florian-asche.de>" ed25519 cert 0
```

Leave the passphrase empty. Then print the fingerprint and create the signing subkey (valid for two years):

```bash
gpg --list-keys --with-colons | awk -F: '/^fpr/ {print $10; exit}'
gpg --quick-add-key <FINGERPRINT> ed25519 sign 2y
```

If you have more than one key in your keyring, check that `awk` printed the fingerprint of the new key.

Export only the subkey. The `!` after the subkey ID is required, otherwise GnuPG exports all subkeys:

```bash
gpg --list-keys --with-colons | awk -F: '/^sub/ {print $5; exit}'
gpg --armor --export-secret-subkeys '<SUBKEY-ID>!' > signing-subkey.asc
```

## 2. What goes where

| What | Where |
| --- | --- |
| `signing-subkey.asc` (signing subkey, without the master key) | GitHub secret `APT_GPG_PRIVATE_KEY` in the environment `apt-publish` |
| Master secret key (`gpg --armor --export-secret-keys <FINGERPRINT>`) | Offline backup only (encrypted USB stick or password manager). Never to GitHub. |
| Revocation certificate (`~/.gnupg/openpgp-revocs.d/<FINGERPRINT>.rev`) | Offline backup |
| Public key | Nowhere. The publish job exports it to `picompose-archive-keyring.gpg` on every run. |

## 3. Set up GitHub

In the repository settings (Settings, Environments) create the environment `apt-publish`. Under "Deployment branches and tags" restrict it to `main`, because the publish workflow always runs on the default branch. Then add the secret `APT_GPG_PRIVATE_KEY` to that environment and paste the whole content of `signing-subkey.asc`, including the `BEGIN` and `END` lines.

With the GitHub CLI:

```bash
gh api -X PUT repos/florian-asche/PiCompose-Repository/environments/apt-publish
gh secret set APT_GPG_PRIVATE_KEY --env apt-publish \
  --repo florian-asche/PiCompose-Repository < signing-subkey.asc
shred -u signing-subkey.asc
```

## 4. Expiry and renewal

The subkey expires after two years. To renew it:

1. Import the master key into a temporary keyring.
2. Extend the subkey: `gpg --edit-key <FINGERPRINT>`, then `key 1`, `expire`, `save`.
3. Export the subkey again (step 1) and replace the secret `APT_GPG_PRIVATE_KEY`.
4. Roll out the updated `picompose-archive-keyring.gpg` to devices **before** the old expiry date. Devices keep the old public key with the old expiry date, so they stop trusting the repository once it has passed. The package `picompose-archive-keyring` ([PiCompose-Package-Archive-Keyring](https://github.com/florian-asche/PiCompose-Package-Archive-Keyring)) is the way to deliver this.

Put the expiry date in a calendar.

## 5. If the secret leaks

Anyone who holds the subkey can sign packages that devices trust. In that case:

1. Revoke the subkey with the master key (`gpg --edit-key <FINGERPRINT>`, `key 1`, `revkey`).
2. Create a new signing subkey and replace the secret.
3. Roll out the new `picompose-archive-keyring.gpg` to devices.
4. Delete the old secret from GitHub.

If the master key leaks, use the revocation certificate and start with a new key.
