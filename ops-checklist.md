# Operator Security Checklist

This document is the reference companion to the **Operator Security Checklist** appended to every Inference Recon report. The report emits a compact checklist; this document explains *why* each item is there and what "verified" actually means in practice.

The fundamental limitation of a code review — automated or manual — is that it can only assess what is visible in the source. An application can have a clean codebase and still be trivially compromised because of how it is deployed, operated, or accessed. This checklist covers that gap.

These are not theoretical risks. The items below map to real-world breach patterns: leaked credentials in git history, lapsed SSL certificates, publicly exposed database ports, shared passwords that outlived former employees, DNS records pointing to abandoned infrastructure. None of these are findable by reading source code.

---

## 1. Infrastructure

### TLS/SSL
**Item:** TLS certificate is valid, auto-renews, and uses a strong cipher suite (TLS 1.2+ only; TLS 1.0/1.1 disabled).

A lapsed certificate breaks your app for users and removes transport encryption. Weak protocol versions (TLS 1.0, TLS 1.1) and cipher suites (RC4, DES, export-grade) are exploitable via known attacks (POODLE, BEAST, BEAST). Auto-renewal prevents the lapse; configuration prevents the downgrade.

To verify: run your domain through `ssllabs.com/ssltest`. An A or A+ grade means you're in good shape.

### Server patching
**Item:** Server OS is patched and running a supported version.

Unpatched Linux kernels and system libraries (OpenSSL, glibc) have real exploits. An attacker who can reach your server can often escalate from a web vulnerability to OS control if the underlying system is unpatched. If your OS version is end-of-life, your hosting provider is no longer shipping security updates for it.

### SSH hardening
**Item:** SSH access requires key-based authentication; password auth is disabled.

Password-based SSH is brute-forced continuously by automated scanners. Key-based auth eliminates this entire class of attack. Check `/etc/ssh/sshd_config` for `PasswordAuthentication no`.

### Firewall
**Item:** Firewall exposes only the ports your application requires (80, 443); database and admin ports are not publicly reachable.

Database ports (5432 for Postgres, 3306 for MySQL, 27017 for Mongo, 6379 for Redis) should never be publicly reachable. If they are, an attacker doesn't need to compromise your app — they can connect directly. The same applies to admin dashboards, internal metrics endpoints, and development servers that were never intended to be public.

### Database transport security
**Item:** Database connections are encrypted in transit (TLS).

Without this, database credentials and query results travel in plaintext across your network. Relevant even for "internal" traffic if you're on a shared cloud network.

### Encryption at rest
**Item:** Data at rest is encrypted (disk encryption on the host, DB encryption at-rest enabled).

If a physical disk or cloud volume is accessed by someone who shouldn't have it (disgruntled hosting provider employee, seized hardware, misconfigured backup), encryption at rest is the last line of defense.

### Backups
**Item:** Backups exist, are encrypted, are stored separately from the production system, and a restore has been tested. **→ t4-playbook.md §2**

A backup stored on the same server it's backing up is destroyed in the same incident. An unencrypted backup is a second copy of your data with weaker access controls. A backup that has never been tested is not a backup — it's an assumption. "Our database was backed up" followed by "but we couldn't restore from it" is a common disaster story.

---

## 2. Access & Secrets

### MFA on privileged accounts
**Item:** All privileged accounts (cloud provider, server, GitHub, domain registrar) use MFA.

Cloud console, GitHub, and domain registrar accounts are extremely high-value targets. A compromised cloud account can destroy infrastructure. A compromised GitHub account can inject malicious code. A compromised registrar account can redirect your entire domain. Password-only protection is insufficient for any of these.

### SSH key attribution
**Item:** Production SSH keys are attributed to known individuals; no shared or unattributed keys exist.

Shared SSH keys cannot be individually revoked. If a team member leaves and their access is "revoked" by rotating a shared password (but not the key), they may still have access. Every key in `~/.ssh/authorized_keys` on your production server should belong to a specific named person who currently needs that access.

### Secrets in the right place
**Item:** Secrets are stored in a secrets manager or vault, not in files on disk, in chat history, or in email.

The code review catches hardcoded secrets in source. This item covers the other places secrets end up: `.env` files with lax permissions, Slack messages, email threads, local shell history, shared Google Docs, or tickets. "In a secrets manager" means something like AWS Secrets Manager, Vault, 1Password Secrets Automation, or at minimum a password manager with access controls. Not a text file.

### Access hygiene
**Item:** Former team members' access has been revoked; you know who currently has production access. **→ t4-playbook.md §3**

Access accumulates. Contractors, freelancers, former co-founders, vendors — they all may have been granted access that was never removed. If you can't name every person with production access and say why they still need it, this item is not verified.

### Least-privilege API keys
**Item:** Application API keys are scoped to least privilege (not using root/admin keys for routine operations).

An API key with "administrator" or "full access" permissions that gets leaked gives an attacker full control of whatever service it accesses. An API key scoped to "read-only access to the orders table" limits the blast radius of the same leak. Most cloud and SaaS providers support scoped tokens; use them.

---

## 3. Build Pipeline

### Branch protection
**Item:** Main branch has push protection (no force-push; changes require PR).

Without branch protection, anyone with write access to the repo can push directly to main — bypassing code review and potentially injecting malicious code. Force-push to main can rewrite history and erase audit trails.

### CI/CD secrets
**Item:** CI/CD secrets are stored as platform secrets, not hardcoded in workflow files.

GitHub Actions, CircleCI, and similar platforms provide encrypted secret storage that prevents secrets from appearing in logs or being readable from forks. Hardcoded secrets in `.github/workflows/*.yml` are visible to anyone who can read the repo.

### Pinned action versions
**Item:** CI/CD actions or runners are pinned to reviewed versions (e.g., `uses: actions/checkout@v4.1.1` not `@main`).

A CI action pinned to `@main` or `@latest` will automatically use new versions of that action — versions you haven't reviewed. A compromised or malicious action maintainer can inject code that exfiltrates your CI secrets. Pin to a specific commit SHA or at minimum a specific version tag.

### Dependency review
**Item:** Dependency update PRs are reviewed before merge.

Dependabot and Renovate auto-PRs are useful, but auto-merging them without review means you're accepting untrusted code changes. A maintainer takeover of a popular package can result in malicious code shipping to your production app via an auto-merged Dependabot PR.

---

## 4. DNS & Domain

### Registrar security
**Item:** Domain registrar has MFA enabled and transfer lock set. **→ t4-playbook.md §1**

A domain registrar account with only a password can be taken over by phishing or credential stuffing. Transfer lock prevents your domain from being transferred to another registrar without explicit approval. These are the two basic controls that prevent domain hijacking — one of the most catastrophic single-point failures for any internet-facing service.

### Dangling DNS
**Item:** DNS records are clean — no dangling CNAMEs pointing to decommissioned services.

When you decommission a Heroku app, Netlify site, S3 bucket, or cloud VM, the CNAME or A record in DNS may still exist. Anyone who claims that hostname at the provider can serve content from your subdomain — including phishing pages, malware, or credential-harvesting forms on a subdomain your users trust. This is subdomain takeover and it is common.

### Certificate monitoring
**Item:** SSL certificate expiry is monitored with pre-expiry alerting.

Auto-renewal works until it doesn't. Alerting lets you catch renewal failures before the certificate expires and breaks the site or drops HTTPS.

### Email authentication
**Item:** If the domain sends email: SPF, DKIM, and DMARC records are configured.

Without SPF, DKIM, and DMARC, anyone can send email that appears to come from your domain. This enables impersonation attacks targeting your users. DMARC at minimum with `p=none` gives you visibility into who is sending from your domain; `p=reject` prevents spoofing.

---

## 5. Monitoring & Response

### Log collection
**Item:** Access and error logs are collected and retained.

Without logs, you cannot answer basic questions after an incident: "Was this endpoint accessed before we patched it?" "How many users were affected?" "When did the attacker first appear?" Cloud providers have logging services (CloudWatch, Cloud Logging, etc.); make sure they're enabled and retained for a useful period.

### Security alerting
**Item:** Alerting exists for repeated auth failures, unexpected traffic spikes, and anomalous admin actions.

A brute-force attack generates hundreds of auth failures per minute. An account takeover often starts with one successful login from an unusual geography. Without alerting, you discover these after the damage is done. Basic threshold alerts on failed logins, and notifications on admin-privilege operations, are a minimum viable security monitoring posture.

### Kill switch
**Item:** You can take the application offline quickly if needed. **→ t4-playbook.md §4**

If you discover an active breach, you need to be able to stop the bleeding fast. "Taking the app offline" should be a known, practiced procedure — not something you're figuring out under pressure. Know how to do this for your hosting provider before you need to.

### Incident playbook
**Item:** You have a playbook for credential compromise: who rotates, who is notified, and how fast. **→ t4-playbook.md §5**

When a secret is compromised, speed matters. A Stripe API key can be used to issue fraudulent charges for as long as it's valid. A clear pre-agreed procedure (who rotates, in what order, how users are notified) reduces the window. The playbook doesn't need to be elaborate — a short checklist is enough.

### Provider contact
**Item:** You know how to reach your hosting provider's security team. **→ t4-playbook.md §6**

If you discover a breach that involves your hosting infrastructure — or if your provider suffers a breach that affects you — you need to be able to contact their security team, not just their billing support. Most major providers have an abuse or security contact; find it before you need it.

---

## 6. Third-Party Services

### Third-party data handling
**Item:** Every third-party service that receives user data has been reviewed for its own security posture.

If you send user PII to an analytics provider, payment processor, support platform, or email service, that provider's security posture is now part of your attack surface. A breach at your email provider can expose your users' email addresses even if your code is perfect. This doesn't mean avoiding third-party services — it means making a conscious, informed decision about each one.

### OAuth scope minimization
**Item:** OAuth integrations request only the scopes actually needed.

Requesting `write:all` when you only need `read:profile` means a leaked OAuth token has a much larger blast radius than necessary. Audit the scopes your OAuth integrations request against what you actually use.

### Webhook signature validation
**Item:** Webhooks from third parties validate the request signature before processing.

A webhook endpoint that processes any inbound POST request — without verifying it actually came from the claimed provider — can be triggered by anyone who discovers the URL. Most providers (Stripe, GitHub, Twilio) sign their webhook payloads; validate the signature before acting on the payload.

### Third-party breach notifications
**Item:** You have a process for learning about breaches at providers you depend on. **→ t4-playbook.md §7**

Follow the security advisories and status pages of providers that store your users' data. A breach at your auth provider that you discover three months later (via a news article) rather than immediately (via their notification) significantly extends your exposure window.

---

## 7. Human Factors

### No shared credentials
**Item:** Team members with production access do not use shared credentials. **→ t4-playbook.md §8**

Shared credentials cannot be individually audited or revoked. When someone leaves the team, a shared credential must be rotated for everyone — but this is frequently skipped. Each person with production access should have their own credentials.

### Laptop-to-production gap
**Item:** SSH private keys are passphrase-protected; developer machine compromise doesn't immediately mean production compromise. **→ t4-playbook.md §9**

A stolen or compromised developer laptop with unencrypted SSH keys and cached cloud credentials gives an attacker immediate production access. Passphrase-protected keys require active knowledge to use. Full-disk encryption on developer machines provides a similar backstop.

### Offboarding
**Item:** There is a clear process for revoking access when someone leaves the team. **→ t4-playbook.md §10**

Access revocation is consistently the most overlooked operational security task. A formal checklist — SSH keys removed, cloud IAM revoked, GitHub org removed, third-party service accounts closed, shared passwords rotated — run at every offboarding, regardless of how the departure went, is essential.

---

## How to use this document

The report checklist is intentionally terse — a quick scan, not a tutorial. When a checklist item is unclear or you want to understand the risk before acting, find the corresponding section here.

Items marked **→ t4-playbook.md** cannot be assessed by any automated tool — they require organisational action. `t4-playbook.md` provides a step-by-step procedure and a fill-in template for each of them.

The checklist is not a compliance framework. It is not exhaustive. It covers the most commonly exploited gaps in small-to-medium web application deployments. A more comprehensive security program would include penetration testing, formal threat modeling, compliance audits, and red team exercises — all of which are outside this tool's scope.

Consider this the floor, not the ceiling.
