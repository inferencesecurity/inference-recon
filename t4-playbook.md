# T4 Playbook: Operator Security — Meatspace Procedures & Templates

This document covers the items in the operator security checklist that no automated tool can verify. They are T4 items: answers live in people's heads, in admin consoles, or in organisational practice — not in source code or external APIs.

The structure for each item:
- **What "done" looks like** — the acceptance criterion
- **How to get there** — step-by-step procedure
- **Template / artifact** — the durable thing left behind after completing it
- **Revisit cadence** — how often to re-verify

These are universal. None of this changes based on your stack.

---

## 1. Domain registrar: MFA enabled, transfer lock set

### What "done" looks like
You log into your registrar, see MFA active (ideally TOTP, not SMS), and the domain transfer lock is enabled. Takes two minutes to verify.

### How to get there

**Cloudflare Registrar:** Account → Profile → Authentication → Two-Factor Authentication → Enable. Domains are transfer-locked by default in Cloudflare; verify under Domains → your domain → Configuration → Transfer lock = Locked.

**Namecheap:** Profile → Security → Two-Factor Authentication → Enable. Domain transfer lock: Domain List → Manage → Domain → Transfer lock = On.

**GoDaddy:** Account Settings → Login & PIN → 2-Step Verification → Set Up. Domain lock: My Products → your domain → Settings → Domain lock = On.

**Squarespace Domains (formerly Google Domains):** Account → Security → 2-Step Verification. Transfer lock: Domains → your domain → Security → Transfer lock = Locked.

**Porkbun:** Account → Account Settings → Two-Factor Auth. Transfer lock is on by default for new registrations.

Use TOTP (Google Authenticator, Authy, 1Password) rather than SMS wherever the registrar offers it. SMS is vulnerable to SIM-swap; TOTP is not.

### Template — registrar security log

```
Domain: ___________________________
Registrar: ________________________
Date verified: ____________________
MFA type: [ ] TOTP  [ ] SMS  [ ] None
Transfer lock: [ ] Enabled  [ ] Disabled
Verified by: _______________________
Next review: _______________________ (annually)
```

### Revisit cadence
Once to set up; annually to verify it hasn't been accidentally disabled. Re-verify immediately after any account recovery or support interaction.

---

## 2. Backup restore has been tested

### What "done" looks like
A full or representative restore from your most recent backup has been executed in a test environment, the data was verified, and the result was documented with a date and a name.

"We have backups" is not done. "We restored from backup on [date] and verified [what]" is done.

### How to get there

1. **Identify your backup source.** Most commonly: managed database backups (RDS automated snapshots, Supabase backups, PlanetScale branching), object storage exports, or a cron job dumping to S3/R2/Backblaze.

2. **Spin up a test environment.** A local database or a temporary cloud instance works. Do not restore into production.

3. **Execute the restore.** For Postgres: `pg_restore -d testdb backup.dump`. For MySQL: `mysql testdb < backup.sql`. For managed services: follow the provider's restore UI but target a test instance.

4. **Verify integrity.** At minimum: row counts on your most important tables match production expectations. Better: run your test suite against the restored DB. Better still: spot-check a handful of records you know should exist.

5. **Document it.** Fill in the template below.

6. **Time it.** Note how long the restore took. This is your recovery time estimate — you want to know this *before* you need it under pressure.

### Template — restore test log

```
Date: ______________________________
Performed by: ______________________
Backup source: _____________________
Backup date/snapshot: ______________
Restore target: ____________________ (never production)
Restore method: ____________________
Time to restore: ___________________

Verification checks:
  [ ] Row count: _____________________ (table: ___________)
  [ ] Row count: _____________________ (table: ___________)
  [ ] Spot check: ____________________
  [ ] Application smoke test: [ ] Pass  [ ] Fail

Notes / anomalies: __________________
____________________________________

Next restore test due: ______________ (quarterly recommended)
```

### Revisit cadence
Quarterly. Run it before you need it, not after.

---

## 3. Former team members' access revoked

### What "done" looks like
You can produce a current access roster — who has access to what — and verify that no one on the list is a former team member, contractor, or vendor whose engagement has ended.

### How to get there

1. **Build the roster** (see template below). List every person and every access point. Do this once; maintain it ongoing.

2. **Compare against current team.** Anyone on the access roster who is no longer actively engaged should be flagged.

3. **Revoke flagged access.** Work through the offboarding checklist (§10) for each flagged person.

4. **Audit trigger:** Run a fresh audit whenever someone departs, and schedule a standing audit quarterly even if no one has left.

### Template — access roster

```
Last audited: ______________________
Audited by: ________________________

| Name | Role | GitHub | Cloud IAM | Server SSH | DB Access | Third-party services | Notes |
|------|------|--------|-----------|------------|-----------|----------------------|-------|
|      |      |        |           |            |           |                      |       |

Current team (expected to appear above): ___________________
Anyone on roster NOT on current team: ____________________ → run offboarding checklist
```

### Revisit cadence
On every departure (immediately). Quarterly audit regardless.

---

## 4. Kill switch: procedure known and practiced

### What "done" looks like
Any team member who might need to act in an emergency can take the application offline in under five minutes, from a personal device, without needing to ask anyone else. The procedure has been run at least once in a non-emergency context.

### How to get there

1. **Write the procedure** for your specific hosting setup (see template). Be specific — "scale to zero" on Fly.io is two commands; "stop a DigitalOcean droplet" is one click.

2. **Test it.** Do it on staging. Or do it on production in a scheduled maintenance window. Time yourself.

3. **Store the procedure somewhere accessible outside your production systems.** If your infrastructure is down, you may not be able to read docs hosted on it. Options: a team password manager note, a printed card, a pinned Slack message, a note on your phone.

4. **Make sure more than one person knows it.** Bus factor of one on a kill switch is a risk.

### Template — kill switch runbook

```
Application: _______________________
Last tested: _______________________ by: ________________

## To take [app] fully offline

### Option A: [fastest method, e.g. "Stop the service"]
1. ____________________________________________________
2. ____________________________________________________
3. ____________________________________________________
Expected downtime: immediate / ~N minutes
Reversible: [ ] Yes — how to restart: ________________

### Option B: [DNS/load balancer cutoff, if applicable]
1. ____________________________________________________
2. ____________________________________________________
Expected time to propagate: ____________________________

### What stays up
[ ] Database (still accessible to internal tools)
[ ] Backups (still running)
[ ] Monitoring/alerting (still running)

## Who can do this
- Name: _________________ Contact: ________________
- Name: _________________ Contact: ________________

## After taking offline, notify
- ___________________________________________________
```

### Revisit cadence
Test once when written; re-test annually or after significant infrastructure changes.

---

## 5. Incident playbook: exists and has been rehearsed

### What "done" looks like
A written playbook exists that any team member can follow during a security incident, and at least one tabletop exercise has been run against a realistic scenario.

A tabletop exercise can be informal: sit down with the team for 30 minutes and walk through "we just discovered an attacker has had read access to the database for two weeks — what do we do?"

### How to get there

1. **Write the playbook** using the template below. Keep it short. A playbook that's too long to read under pressure won't be read.

2. **Run a tabletop.** Pick a realistic scenario (credential leak, data breach, ransomware on a dev machine, compromised dependency). Walk through the playbook step by step. Note where it breaks down or is ambiguous.

3. **Update the playbook** based on what the tabletop revealed.

4. **Store it where it's findable under pressure** — same guidance as the kill switch runbook: accessible outside the systems that might be compromised.

### Template — incident response playbook

```
Last updated: ______________________
Last rehearsed: ____________________ (scenario: _____________)

## Roles (fill in names now, not during incident)
Incident lead: _____________________  Contact: _______________
Technical lead: ____________________  Contact: _______________
Communications lead: _______________  Contact: _______________
Executive/owner notification: _______  Contact: _______________

## Phase 1 — Detection & triage (first 30 minutes)
1. Document what you know: what was observed, when, by whom.
2. Assess: is this confirmed or suspected? What systems are involved?
3. Declare: notify the incident lead. Incident is now active.
4. Preserve evidence: do NOT wipe logs, do NOT restart services yet.
5. Initial containment decision: take offline now, or monitor for 30 more minutes?

## Phase 2 — Containment (first 2 hours)
1. If credentials may be compromised: rotate immediately (see §7 credential rotation).
2. If active attack: take relevant systems offline (see kill switch runbook).
3. Block known attacker IPs at the firewall if identified.
4. Preserve a snapshot of the compromised system before remediation.

## Phase 3 — Notification
Internal notifications:
  - Owner/executive: within [ ] 1h  [ ] 4h  [ ] 24h of confirmation
  - Full team: within ___________

External notifications (only if legally required or user-impacting):
  - Affected users: within ___________ (check your jurisdiction — GDPR: 72h to regulator)
  - Hosting provider: _______________ (see §6 for contacts)
  - Legal/compliance: _______________

## Phase 4 — Remediation
1. Identify root cause (do not skip this).
2. Apply fix. Verify the fix before reopening systems.
3. Rotate any secrets that were or may have been exposed.
4. Re-enable services incrementally; monitor closely.

## Phase 5 — Post-mortem (within 1 week)
1. Timeline of events: when did it start, when was it detected, when contained?
2. Root cause (5-whys or equivalent).
3. What the playbook got right, and where it broke down.
4. Concrete action items with owners and deadlines.
5. Update this playbook.

## Credential rotation order (for common breach scenarios)
1. ___________________________________________________
2. ___________________________________________________
3. ___________________________________________________

## "We've been breached" checklist
[ ] Incident declared, lead assigned
[ ] Evidence preserved (logs, screenshots, timeline)
[ ] Containment in progress
[ ] Legal/compliance notified (if applicable)
[ ] Users notified (if applicable)
[ ] Root cause identified
[ ] Remediation applied and verified
[ ] Post-mortem scheduled
```

### Revisit cadence
Tabletop annually. Update after any real incident. Review whenever the team or infrastructure changes significantly.

---

## 6. Hosting provider security contacts

### What "done" looks like
You know where to go — or have it written down — for each provider that hosts your infrastructure. Under pressure is not the time to search for this.

### Reference: common provider contacts

| Provider | Security / abuse contact | Notes |
|---|---|---|
| AWS | https://aws.amazon.com/security/vulnerability-reporting/ | Also: security@amazon.com for urgent issues |
| Google Cloud | https://cloud.google.com/support/docs/security-incident | security@google.com |
| Azure | https://msrc.microsoft.com/report | Microsoft Security Response Center |
| DigitalOcean | abuse@digitalocean.com / security@digitalocean.com | Also via support ticket marked "Security" |
| Hetzner | abuse@hetzner.com / security@hetzner.com | |
| Vultr | abuse@vultr.com | |
| Fly.io | security@fly.io | |
| Render | security@render.com | |
| Railway | security@railway.app | |
| Heroku (Salesforce) | https://www.salesforce.com/company/legal/security/ | |
| Cloudflare | https://www.cloudflare.com/abuse/ | For DDoS/abuse; also via dashboard support |
| Vercel | security@vercel.com | |
| Netlify | security@netlify.com | |
| Supabase | security@supabase.io | |
| PlanetScale | security@planetscale.com | |
| MongoDB Atlas | security@mongodb.com | |
| GitHub | https://github.com/security | security@github.com for urgent |
| Stripe | security@stripe.com | |
| Twilio | https://www.twilio.com/security | |
| SendGrid (Twilio) | security@sendgrid.com | |
| Mailgun | security@mailgun.com | |

### Template — your provider contact list

```
Fill this in for the providers you actually use. Keep it alongside the kill switch runbook.

| Provider | What it hosts | Security contact | Account email | Notes |
|---|---|---|---|---|
|   |   |   |   |   |
```

### Revisit cadence
Fill in once. Update when you add or change providers.

---

## 7. Process for learning about third-party breaches

### What "done" looks like
You have a passive mechanism to learn about security incidents at providers you depend on — without having to actively check each one.

### How to get there

**Status pages (operational incidents):**
Subscribe to the status page for every provider whose breach would affect your users. Most offer email subscriptions:
- Find via `[provider].com/status` or `status.[provider].com`
- Subscribe with a team alias or your own email

**Security advisories:**
- GitHub: Watch repositories for security advisories (Settings → Notifications → Security alerts)
- npm: `npm audit` in CI catches dependency advisories automatically
- PyPI: Dependabot or `pip-audit` in CI
- Most cloud providers publish a security bulletin RSS feed

**HaveIBeenPwned (HIBP) API:** If you store user email addresses, monitor `haveibeenpwned.com/API/v3` with your domain to be notified when a data breach surfaces your users' emails. There is a free notification API for domain owners.

**For critical providers:** Follow their engineering blog and @security Twitter/X accounts. AWS, Cloudflare, GitHub and Stripe all announce meaningful incidents there.

### Template — provider monitoring list

```
| Provider | Status page subscribed | Security advisory channel | Last checked |
|---|---|---|---|
|   | [ ] Yes  [ ] No |   |   |
```

### Revisit cadence
Set up once; review annually. Actively check during major incidents you read about in the news.

---

## 8. No shared credentials

### What "done" looks like
Every service has individual accounts per person, or — where individual accounts aren't possible — the credential is managed in a team password manager with individual audit trails and is rotated whenever a team member leaves.

### How to get there

1. **Audit.** For every service, ask: can multiple people log in under the same account? Common offenders: old-school hosting panels, legacy admin accounts, shared root@server passwords, a single "company" GitHub account.

2. **Create individual accounts wherever possible.** Most SaaS tools support multiple users. Create per-person accounts; demote or remove the shared one.

3. **Where individual accounts aren't possible** (some hosting panels, legacy services): move the shared credential into a team password manager (1Password Teams, Bitwarden Business, Dashlane Business). This provides: single source of truth, access auditing, and the ability to update the credential once when someone leaves.

4. **Rotate any shared credential immediately when someone leaves.** This is non-negotiable even if the departure was amicable. The offboarding checklist (§10) should list every shared credential to rotate.

### Template — shared credentials audit

```
| Service | Shared? | In team password manager? | Who has access | Last rotated | Action needed |
|---|---|---|---|---|---|
|   |   |   |   |   |   |
```

### Revisit cadence
Audit when onboarding or offboarding anyone. Quarterly sweep.

---

## 9. SSH keys passphrase-protected on developer machines

### What "done" looks like
Every SSH key that grants access to a production system has a passphrase. A stolen laptop does not give an attacker immediate production access.

### How to check if a key has a passphrase

```bash
# If it prompts you for a passphrase: protected. If it just outputs the public key: not protected.
ssh-keygen -y -f ~/.ssh/id_rsa
```

Run this for every key in `~/.ssh/` that has production access.

### How to add a passphrase to an existing key

```bash
ssh-keygen -p -f ~/.ssh/id_rsa
# Enter old passphrase (blank if none), then enter and confirm the new passphrase.
```

### Making passphrase-protected keys usable day-to-day

Using `ssh-agent` means you only type the passphrase once per session:

```bash
# Add to ~/.ssh/config:
Host *
  AddKeysToAgent yes
  UseKeychain yes   # macOS only — stores passphrase in Keychain
  IdentityFile ~/.ssh/id_rsa
```

On macOS, `ssh-add --apple-use-keychain ~/.ssh/id_rsa` stores the passphrase in the system Keychain so it survives reboots.

### As a team practice

Add to your onboarding documentation: "All SSH keys used for production access must have a passphrase. Verify with `ssh-keygen -y -f <keypath>`."

### Revisit cadence
Each team member verifies once when setting up. Re-verify when generating new keys. There is no automated mechanism to enforce this remotely — it relies on team practice and onboarding culture.

---

## 10. Offboarding checklist: used at every departure

### What "done" looks like
A named person runs a specific checklist within 24 hours of every departure — amicable or otherwise — and signs off that each step was completed.

### How to get there

1. **Own the process.** Assign one person responsible for security offboarding (often the tech lead or eng manager). Not "everyone is responsible" — that means no one is.

2. **Copy the template below** into your team's documentation system (Notion, Confluence, GitHub wiki, a shared doc). Customise it for your services.

3. **Run it every time.** No exceptions for "they left on good terms" or "they probably won't do anything." The risk of retaining access is asymmetric to the cost of removing it.

4. **Complete it quickly.** Within 24 hours of departure is the target. Access retained for days after departure is a real exposure window.

### Template — offboarding security checklist

```
Departing team member: _____________
Departure date: ____________________
Completed by: ______________________
Date completed: ____________________

## Code & version control
[ ] Removed from GitHub organisation / GitLab group
[ ] Personal access tokens revoked (GitHub: Settings → Developer Settings → PATs)
[ ] Removed from all private repositories they had direct access to
[ ] Deployment keys they created reviewed and rotated if shared

## Cloud infrastructure
[ ] AWS IAM user deactivated and access keys deleted
[ ] GCP IAM member removed
[ ] Azure AD account disabled / removed from subscription
[ ] DigitalOcean / Hetzner / etc. team membership removed
[ ] SSH public key removed from all servers' authorized_keys:
    [ ] Server: ____________________
    [ ] Server: ____________________

## Third-party services
[ ] Stripe dashboard access removed
[ ] Sentry team removed
[ ] Datadog / New Relic / Grafana team removed
[ ] Vercel / Netlify / Render team removed
[ ] Supabase / PlanetScale / Neon org removed
[ ] CI/CD platform (GitHub Actions / CircleCI / etc.) access removed
[ ] Support tool (Intercom / Zendesk / etc.) account deactivated
[ ] Analytics (Mixpanel / Amplitude / etc.) removed
[ ] Other: _________________________ removed
[ ] Other: _________________________ removed

## Credentials & secrets
[ ] Any API keys they personally generated reviewed; rotated if they had production access
[ ] Shared credentials they knew rotated (list each):
    [ ] ___________________________________________________
    [ ] ___________________________________________________
    [ ] ___________________________________________________

## Access & communications
[ ] Email/Slack/communications account deactivated
[ ] VPN / Tailscale / WireGuard access revoked
[ ] Password manager team membership removed
[ ] Domain registrar access removed (if they had it)
[ ] Any admin dashboard accounts (internal tools, CMS, etc.) disabled

## Final check
[ ] Access roster (§3 template) updated to remove this person
[ ] All of the above confirmed complete

Notes / exceptions: _________________
____________________________________
Signed off: _________________________ Date: _______________
```

### Revisit cadence
Run immediately at every departure. Review the template quarterly to ensure it reflects your current service list — new services get added but the checklist often doesn't keep up.

---

## Quick reference: T4 items and their cadence

| Item | First-time effort | Ongoing cadence |
|---|---|---|
| Registrar MFA + transfer lock | 10 min | Annual verify |
| Restore test | 1–2 hours | Quarterly |
| Access roster + audit | 30 min to build | Every departure + quarterly |
| Kill switch runbook | 30 min to write, 30 min to test | Annual test |
| Incident playbook + tabletop | 2–3 hours | Annual tabletop |
| Provider contacts list | 30 min | When providers change |
| Provider breach monitoring | 30 min to set up | Annual review |
| Shared credentials audit | 1–2 hours | Every departure + quarterly |
| SSH key passphrase verification | 5 min per person | Onboarding + new keys |
| Offboarding checklist | 30 min to customise | Every departure |

Total first-time investment for a small team: approximately one day. Ongoing: a few hours per quarter plus the offboarding trigger.
