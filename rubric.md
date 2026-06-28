# Security Review Rubric

This document tells the reviewing model what to look for. It is **content**, not orchestration — the prompt references this file; this file does not contain prompt logic. The schema (`schema.json`) defines the output contract; this file defines the substantive judgment.

Stack-agnostic by design. Stack-specific guidance lives in `rules/*.md` rule packs that may be appended to this rubric at scan time.

## 1. How the prompt uses this rubric

The prompt walks the model through the four scorecard domains in order: Code, Dependencies, Secrets & Config, Architecture. For each domain, the rubric provides (a) the categories that belong to it, (b) the patterns to look for, and (c) negative anchors — patterns that look like findings but aren't. Every finding emitted by the model carries a `category` from the schema's closed enum; the domain-to-category mapping in §6 below is authoritative.

## 2. Cross-cutting principles

These apply to every finding regardless of domain. They're enforced by the schema where possible (`exploitation_path` requirement, evidence object), and by language where not (severity calibration, what counts as a "real" finding).

**Reachability over presence.** A vulnerable pattern that no caller can reach is not the same as a vulnerable pattern that is exposed via an HTTP route, a CLI argument, or any other untrusted-input boundary. Findings tied to reachable code paths warrant `confidence: high`; pattern matches with unclear exposure warrant `medium` or `low`. The model must say *why* it believes a finding is reachable when it claims so — typically by citing a related location (an entrypoint, an exposed handler, a config that mounts the code path).

**Severity reflects this project's impact, not the upstream worst case.** A vulnerability that exists in the codebase but is reachable only through internal callers warrants lower severity than the same vulnerability on an internet-facing endpoint. When citing a CVE, the `cvss.score` in the finding is the upstream NVD/vendor score (verbatim copy); the finding's `severity` is the model's project-specific assessment. They are allowed — and often expected — to diverge. (See `examples/04-dep-known-cve.md`.)

**Confidence calibration.** Three tiers, with explicit meaning:
- `high` — direct evidence the issue is reachable and exploitable in this codebase. Specific vulnerable code is shown; the path from an untrusted boundary to that code is demonstrated.
- `medium` — pattern matches a known vulnerability class but exploitability in context is uncertain. The model can name the concern but cannot demonstrate the path to exploitation.
- `low` — heuristic match, weak signal, surfaced for completeness. The model believes a reviewer should glance at this but expects most low-confidence findings to be dismissed on review.

The default rendered report suppresses `confidence: low` findings; they remain in the JSON for power users.

**Evidence discipline.** Every finding's `evidence.quote` must be verbatim — exact characters from the source, no paraphrasing or ellipsis. The line range `line_start..line_end` must match the quoted span exactly. For multi-file findings, the primary `evidence` location is where the architectural decision or root cause lives; `related_locations` carry the supporting context. (See `examples/03-arch-missing-authz.md` for the canonical example.)

**Specificity.** Titles, exploitation paths, and remediations must be specific enough to be actionable. "Input validation issue" is not a title; "SQL injection via unescaped `user_id` in `/users/<id>` route" is. "Consider reviewing authentication" is not a remediation; "Apply `login_required_for_blueprint(admin_bp)` immediately before `app.register_blueprint(admin_bp, ...)` in `create_app()`" is.

**Negative reasoning.** When something looks like a vulnerability but isn't on closer inspection, the model should *not* flag it. The cost of a false positive is high: every noisy finding erodes trust in the entire report. When in doubt between flagging at low confidence and not flagging at all, prefer the latter for v1.

## 3. Domain: Code-level vulnerabilities

**Scorecard bucket:** `code`.
**Categories:** `CODE_injection`, `CODE_crypto_failure`, `CODE_input_validation`, `CODE_unsafe_api_use`, `AUTHN_failure`, `AUTHZ_failure`, `INTEGRITY_failure`.

This is the most familiar ground — what a SAST tool would chase. The model's job here is not to compete with rule-based scanners on completeness but to add reasoning the rules-based world struggles with: data flow across functions, whether a sink is actually reached, whether a sanitizer is sufficient for the context.

**Injection (`CODE_injection`).** Any place untrusted data flows into an interpreter and the data is not separated from the code by a parameterized API. Common interpreters: SQL engines, OS shells, template engines, expression evaluators, regex (ReDoS), LDAP queries, XPath/XQuery, NoSQL query languages, header parsers, and the HTML/DOM renderer. The signal is *concatenation or interpolation of untrusted data into a structured string that is then executed*. Parameterized APIs (prepared statements, parameterized template render calls, `textContent`/`innerText` for DOM, etc.) are the absence-of-finding indicator.

**Cross-site scripting (`CODE_injection`).** XSS is injection into the HTML/DOM interpreter — the same category as SQL injection, just a different interpreter. Two surfaces to assess:

- *Server-side template rendering:* Untrusted data rendered without escaping. Dangerous patterns: Jinja2/Twig `{{ var | safe }}` or `{% autoescape false %}`, Thymeleaf `th:utext`, EJS `<%-`, Handlebars/Mustache triple-stache `{{{ var }}}`, Freemarker `?no_esc`, Python string formatting directly into HTML. The safe equivalent in each case is the default auto-escaped syntax.
- *Client-side DOM sinks:* Untrusted data (from URL params, `localStorage`, API responses, user-supplied content) assigned to dangerous properties or functions: `innerHTML`, `outerHTML`, `document.write()`, `document.writeln()`, jQuery's `.html()` / `.append()` / `.prepend()` with untrusted strings, React's `dangerouslySetInnerHTML`, Angular's `bypassSecurityTrustHtml`. The safe equivalent is `textContent` / `innerText` or framework-provided sanitization.

Stored XSS (content written to a database and later rendered to other users) is generally higher severity than reflected XSS (content echoed immediately back to the same request). Both are findable from source: stored XSS requires tracing from the write path (POST handler → DB insert) to the render path (GET handler → template render); reflected XSS is a single-step trace from request parameter to output. DOM-based XSS requires tracing untrusted sources (`location.search`, `location.hash`, `document.referrer`, `localStorage`, `postMessage`) to DOM sinks within client-side JavaScript.

**Cryptographic mistakes (`CODE_crypto_failure`).** Weak algorithms (MD5, SHA1 for security-relevant hashing, DES, RC4); ECB mode block ciphers; hardcoded or default IVs; predictable randomness (`random.random()`, `Math.random()`, time-based seeds for security purposes); JWT mistakes (none algorithm, no signature verification, signature verification with the wrong key class); TLS misuse (verification disabled, custom verifier that accepts anything, hostname check disabled); password storage without a memory-hard KDF (bcrypt, scrypt, argon2 are correct; PBKDF2 with very low iterations is suspect).

**Input validation (`CODE_input_validation`).** Missing or insufficient validation at trust boundaries — function entry points, deserialization sites, URL parsing. Distinguish from injection: an injection finding is about *output* into a sensitive sink without escaping; an input validation finding is about *input* not being constrained at all (which then enables injection or other issues downstream). When both apply, prefer the more specific finding.

**Unsafe API use (`CODE_unsafe_api_use`).** Catch-all for code-level misuse of dangerous APIs. Includes unsafe deserialization (pickle, YAML's unsafe loaders, Java's ObjectInputStream, .NET BinaryFormatter); path traversal via unchecked path joining; race conditions in security-sensitive code (TOCTOU); use of `eval`, `exec`, `Function()`, dynamic require/import with untrusted input; dangerous defaults left in place (CORS wildcard origins, `debug=True` in code rather than config — though framework-level debug toggles belong in `CONFIG_insecure_default`).

**Authentication (`AUTHN_failure`).** Code-level authentication flaws: password reset tokens that don't expire or aren't cryptographically tied to the user, session IDs that don't rotate on privilege change, MFA flows that can be bypassed by direct request to a post-MFA endpoint, credential checks via string comparison that allow timing attacks, "remember me" tokens stored in localStorage without rotation. Does NOT cover missing authentication entirely on an endpoint that should require it — that's `ARCH_missing_authz` (if a whole class of endpoints) or `AUTHZ_failure` (if a single missed check).

**Authorization (`AUTHZ_failure`).** Code-level authz flaws: a specific handler that should call a permission check and doesn't; role confusion (treating a normal user object as admin because of a type confusion); IDOR-style flaws where the handler trusts user-supplied IDs without verifying ownership; horizontal privilege escalation paths. Per the taxonomy disambiguation rule, prefer `ARCH_missing_authz` when the gap is architectural (an entire endpoint class lacks an authz layer); use `AUTHZ_failure` when a specific code-level check is missing or incorrect.

**Integrity (`INTEGRITY_failure`).** OWASP A08 territory: software/data integrity failures. Unsigned update mechanisms; plugin or extension loading from untrusted sources; deserialization of trusted-by-mistake data; CI/CD pipelines that pull dependencies without integrity verification. The signal is: the code trusts something it shouldn't, and there's no integrity check to catch tampering.

**What is NOT a code-level finding.** Defense-in-depth recommendations ("you could also add CSRF tokens here") are not findings unless the absence creates a real exposure. Style or maintainability issues that have no security impact are not findings. Pattern-matched calls to APIs that are *also* used correctly elsewhere are not findings just because the API is dangerous — the finding requires demonstrating the unsafe use, not just the API presence.

## 4. Domain: Dependencies & supply chain

**Scorecard bucket:** `dependencies`.
**Categories:** `DEP_known_cve`, `DEP_supply_chain_risk`.

This domain is the one where existing scanners (Snyk, Dependabot, GitHub Advisory) genuinely excel. The model should not pretend to maintain a CVE database from memory; it should flag what it can confidently identify and acknowledge the limit.

**Known CVEs (`DEP_known_cve`).** A dependency pinned to a version with a publicly known CVE that the model can confidently identify by name. Required fields when claiming this: the `references` array contains a CVE ID matching `CVE-\d{4}-\d+`; the `cvss` object carries the upstream NVD or vendor-published vector and score (verbatim — the model does NOT author these); confidence reflects the model's certainty about *both* the version being vulnerable and the code path being reachable.

Higher confidence requires showing the call site. Lower confidence is appropriate when the version is vulnerable but no specific exploitable usage is identified. (See `examples/04-dep-known-cve.md`.)

**Supply-chain risk (`DEP_supply_chain_risk`).** Concerns beyond a specific known CVE: floating version ranges with no lockfile (so the next install picks up unknowable code); typosquatting (`reqeusts` vs `requests`, etc.); recently-published packages with thin maintainer history pulled into critical paths; transitive dependencies on abandoned packages; packages installed from unofficial registries or git URLs; missing lockfile integrity hashes.

**What is NOT a dependency finding.** "This dependency is two minor versions behind" is not a finding without a specific CVE or supply-chain concern attached. Pinning to a specific version is the correct practice, not a finding. License concerns are out of scope for security review (compliance-adjacent, but not this tool's job — per §4 of the design doc).

## 5. Domain: Secrets & configuration

**Scorecard bucket:** `secrets_and_config`.
**Categories:** `SECRET_hardcoded`, `SECRET_committed_history`, `SECRET_logged`, `CONFIG_insecure_default`, `CONFIG_excessive_permission`, `CONFIG_iac_misconfig`.

The signal-to-noise ratio in this domain depends entirely on the model's discipline about *what is and isn't a real secret*. Half the value of this domain is suppressing the false positives.

**Hardcoded secrets (`SECRET_hardcoded`).** A credential present in current source. Two distinct signals together strongly indicate a real secret: (a) the string has an identifiable real-secret prefix or format (`sk_live_`, `AKIA`, `ghp_`, `xoxb-`, `-----BEGIN PRIVATE KEY-----`, GitHub PATs, JWT-shaped tokens with non-test claims, etc.), and (b) the surrounding context confirms it's used as a real credential (assigned to an API client, sent in an Authorization header). Either signal alone is weaker. A high-entropy random-looking string with no contextual confirmation could be a hash, a test fixture, a tracking ID, or any number of innocent things.

Always-flag prefixes (when value body is non-placeholder): `sk_live_`, `AKIA`, `ASIA`, `ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, `xoxb-`, `xoxp-`, `slack-`, `-----BEGIN (RSA|EC|OPENSSH|ENCRYPTED) PRIVATE KEY-----`.

(See `examples/02-secret-hardcoded.md` for severity calibration: `sk_live_` warrants `critical` because it's identifiable as a live production secret.)

**Secrets in git history (`SECRET_committed_history`).** Secret present in the repository's git history even if removed from current code. Treat history as compromised regardless of current state — the credential must be rotated. The model can only flag this when given visibility into history (`git log -p`); when working from a working tree only, this category may be inferable from comments ("rotated after the last leak") or from explicit notes.

**Secrets in logs (`SECRET_logged`).** Logger calls or error paths that emit credentials, full request headers, cookies, or other sensitive material. Look for patterns like `logger.info(f"...{api_key}...")`, exception handlers that log full request objects, debug prints in production paths.

**Insecure framework defaults (`CONFIG_insecure_default`).** Framework or runtime configuration left at an insecure default. Examples that recur across stacks: debug mode left on in production; default `SECRET_KEY` or session secret unchanged from documentation example; CORS configured with wildcard `*` origin for credentialed requests; cookie flags missing (`Secure`, `HttpOnly`, `SameSite`); HTTP server bound to `0.0.0.0` when only localhost was intended; TLS configuration accepting weak protocol versions.

**Excessive permissions (`CONFIG_excessive_permission`).** IAM, file, process, or service permissions broader than necessary. Cloud IAM policies with `*:*` actions, file permissions of `0777`, services running as root unnecessarily, Kubernetes pods with `runAsUser: 0` or `privileged: true` without justification.

**IaC misconfiguration (`CONFIG_iac_misconfig`).** Terraform, CloudFormation, Kubernetes manifests, or Helm charts that provision resources insecurely: S3 buckets with public-read ACLs, security groups with `0.0.0.0/0` ingress on sensitive ports (22, 3389, database ports), unencrypted storage volumes, public-facing load balancers without WAF, secrets stored in plain ConfigMaps instead of Secrets, missing network policies.

**What is NOT a secrets/config finding.** Placeholder secrets in test fixtures (`sk_test_...`, `password = "test"`, `API_KEY = "REPLACE_ME"`) are not findings — they're intentional and serve documentation/testing purposes. Environment variable references (`os.environ['STRIPE_KEY']`) are not findings — they're the correct pattern. Default values that are intentionally public (e.g., a public OAuth client ID, which is not secret by design) are not findings. CORS wildcard for endpoints that are intentionally public and do not accept credentials is not a finding.

## 6. Domain: Architecture & threat modeling

**Scorecard bucket:** `architecture`.
**Categories:** `ARCH_trust_boundary`, `ARCH_missing_authz`, `ARCH_data_flow_risk`, `ARCH_attack_surface`, `ARCH_logging_gap`, `INSECURE_DESIGN`, `OTHER`.

This is the v1 differentiator. Per R5, `ARCH_*` findings carry the highest hallucination risk and the schema enforces a higher evidence bar (`exploitation_path` required regardless of severity). The model should approach this domain with discipline: vague architectural concerns ("consider reviewing the overall design") are not findings — concrete claims with concrete evidence are.

**Trust boundaries (`ARCH_trust_boundary`).** Untrusted data crosses into a trusted context without adequate validation or sanitization at the crossing. Look for: HTTP request data being deserialized and passed into business logic without a schema check; webhook payloads being trusted because they arrived on an "internal" endpoint; message queue consumers treating message bodies as well-formed because the producer is "trusted"; data crossing from a worker process to a privileged process without an audit. The signal is *the absence of a check at the crossing*, not just the presence of data flow.

**Missing authorization (`ARCH_missing_authz`).** An entire endpoint class or subsystem lacks an authorization layer. Distinct from `AUTHZ_failure`, which is a code-level missed check at a specific point. Strong heuristic: **asymmetry**. If one part of the codebase has a protection (an `@login_required` decorator, a blueprint-level auth middleware, a guard route) that an analogous part lacks, that asymmetry is direct evidence the protection was intended. (See `examples/03-arch-missing-authz.md` — the killer-feature example.)

**Data flow risk (`ARCH_data_flow_risk`).** Sensitive data traveling on an insecure path or persisted insecurely. Examples: PII transmitted over HTTP (not HTTPS) between internal services; credit card numbers logged to plain log files; passwords stored in plaintext or with reversible encoding; sensitive data placed in URL query strings (where it ends up in proxy logs and browser history); JWTs containing sensitive claims being put in places they shouldn't be (localStorage, URL fragments).

**Attack surface (`ARCH_attack_surface`).** Unnecessary attack surface exposed. Debug endpoints reachable in production (`/debug`, `/admin/console`, `/metrics` without auth); internal-only services bound to public network interfaces; cloud metadata service accessible from application code paths (SSRF risk); legacy or deprecated API versions still mounted; admin UI on the same host:port as the public API.

**Logging gaps (`ARCH_logging_gap`).** Security-relevant events not logged, making detection and forensics impossible. Authentication successes/failures not logged; authorization denials not logged; admin actions not audited; high-privilege role grants not recorded; sensitive data access not tracked. The finding requires identifying an *operation* that should be logged and demonstrating that no logging exists at that point.

**Insecure design (`INSECURE_DESIGN`).** OWASP A04. Business logic flaws and design-level issues that aren't best described by the more specific categories. Examples: password reset flows that disclose whether an account exists; rate limiting absent on operations that need it (login attempts, password resets, OTP submissions); single-step destructive operations on shared resources without confirmation tokens; race conditions in business workflows (the classic "transfer money twice from one balance").

**OTHER (escape hatch).** Findings that genuinely don't fit any other category. When the model uses `OTHER`, an entry in the envelope `notes` array must explain why no other category applied. This category is part of the architecture scorecard bucket by default.

**What is NOT an architecture finding.** Designs the model disagrees with stylistically but that don't create a concrete security exposure are not findings ("REST would have been better than RPC here" — not a finding). Endpoints that are intentionally public are not `ARCH_missing_authz` findings; look for *asymmetry* with related protected endpoints or for explicit context indicating the public exposure is by design. Speculative attack scenarios that require multiple unfounded assumptions chained together are not findings — the exploitation path must be plausible with no missing premises.

## 7. Category-to-scorecard mapping (authoritative)

The scorecard derivation uses this mapping. Every category in the schema enum belongs to exactly one bucket.

| Scorecard bucket | Categories |
|---|---|
| `code` | `CODE_injection`, `CODE_crypto_failure`, `CODE_input_validation`, `CODE_unsafe_api_use`, `AUTHN_failure`, `AUTHZ_failure`, `INTEGRITY_failure` |
| `dependencies` | `DEP_known_cve`, `DEP_supply_chain_risk` |
| `secrets_and_config` | `SECRET_hardcoded`, `SECRET_committed_history`, `SECRET_logged`, `CONFIG_insecure_default`, `CONFIG_excessive_permission`, `CONFIG_iac_misconfig` |
| `architecture` | `ARCH_trust_boundary`, `ARCH_missing_authz`, `ARCH_data_flow_risk`, `ARCH_attack_surface`, `ARCH_logging_gap`, `INSECURE_DESIGN`, `OTHER` |

The `overall` grade is the worst non-N/A bucket grade. The full derivation algorithm (finding_score = severity_weight × confidence_weight, thresholds 10/5/2/1 → F/D/C/B/A) is specified in `report-template.md` §10 and `prompt.md` Step 6.

## 8. Data sensitivity and severity calibration

The `data_profile` object is produced in Step 1.5 of the prompt, before any findings are assessed. It is the risk multiplier: the same finding has materially different implications depending on what data it could expose.

**Sensitivity tiers and their meaning for severity calibration:**

| Tier | What it means | Severity calibration |
|---|---|---|
| `minimal` | Email/username/session data only. No regulatory triggers. | No adjustment. Grade findings on their own technical merit. |
| `standard` | Contact info, basic profile. GDPR/CCPA may apply. | No automatic adjustment, but note user-impact in `exploitation_path`. |
| `elevated` | Government IDs, precise financial metadata, location history. | When a finding could expose elevated-tier data, prefer the higher severity bucket if on the boundary. State this in `exploitation_path`. |
| `high` | Payment card data (PCI), PHI (HIPAA), biometrics, GDPR special categories. | A finding that could expose high-tier data gets the higher severity tier. A boundary call between `high` and `critical` resolves to `critical`. State the regulatory implication explicitly in `exploitation_path`. |
| `critical` | Multiple high categories, or children's data. | Any finding that could expose critical-tier data is `critical` severity. No boundary cases. |

**Soft escalation rule (apply to all domains):** When the data profile establishes a `high` or `critical` tier *and* a finding's exploitation path plausibly exposes that data class, bias to the more severe tier. This is not automatic escalation — it requires the model to reason that the data type is actually reachable via the vulnerability. A SQL injection on a table that provably contains PHI is different from a SQL injection on a logging table. Demonstrate the connection in `exploitation_path`.

**Practical examples:**
- SQL injection (`CODE_injection`) on a users table containing email + SSN → `critical` at `high` tier (identity theft, breach notification trigger), not `high`.
- CORS wildcard (`CONFIG_insecure_default`) in a `minimal` app → `medium` as normal. Same finding in a `high`-tier app where the wildcard origin could read PHI endpoints → `high`.

**What to look for when building the data profile:**

*Model and schema definitions:* ORM models (`class User(db.Model)`, Prisma schema, Mongoose schema, ActiveRecord migrations, TypeScript interfaces) are the richest source. Field names are usually explicit: `ssn`, `date_of_birth`, `diagnosis`, `card_number`, `routing_number`, `insurance_id`.

*Migration files:* SQL/ORM migrations name columns directly and are highly reliable evidence. `ALTER TABLE patients ADD COLUMN diagnosis TEXT` is unambiguous.

*Validation schemas:* Pydantic models, Zod schemas, Joi schemas, OpenAPI specs reveal what data is accepted at API boundaries — often more complete than model definitions.

*Third-party SDK imports:* These are strong proxies for data type even when field names are absent.

| SDK / import | Data category signal |
|---|---|
| `stripe`, `braintree`, `square`, `adyen` | `financial_payment` |
| `plaid`, `yodlee`, `finicity` | `financial_account` |
| `hl7`, `fhir`, `epic`, `cerner`, any `*ehr*` | `health_phi` |
| `twilio`, `vonage`, `nexmo` | `contact_info` (phone numbers) |
| `aws-rekognition`, `azure-face`, `deepface` | `biometric` |
| `persona`, `stripe-identity`, `jumio`, `onfido` | `government_id` |
| Any library with `coppa`, `child`, `minor`, `under13` | `childrens_data` |

*Environment variable names:* `STRIPE_SECRET_KEY`, `PLAID_CLIENT_ID`, `HIPAA_COMPLIANT`, `PCI_MODE` are strong signals even when the SDK import isn't visible.

*Documentation and READMEs in the repo:* Developers often state data handling explicitly ("This service stores patient records", "We process credit card payments via Stripe").

*Test fixtures:* Fake SSNs, dummy card numbers, and example PHI in test data reveal what the real schema expects.

**What is NOT a data category signal.** A field named `user_token` is not necessarily `auth_credentials` without context. A field named `location` could be a UI locale, not GPS coordinates. Apply the same confidence discipline used for findings: `high` confidence requires clear, specific evidence; `medium` is a reasonable inference; `low` is a heuristic that might be wrong.

**Regulatory flag applicability rules:**

| Regulation | Flag as `likely` when… | Flag as `possibly` when… |
|---|---|---|
| PCI-DSS | `financial_payment` detected with high confidence | `financial_payment` detected at medium confidence, OR Stripe/payment SDK present but card data may not touch the server |
| HIPAA | `health_phi` detected with high confidence | Healthcare-adjacent SDK or field names present but PHI scope unclear |
| GDPR | Any personal data + evidence of EU market (`.eu` domain, `locale: 'de'`, EU-specific copy) | Any personal data collection without EU market signal |
| CCPA | Any personal data + evidence of California/US market at meaningful scale | Any US-facing consumer app collecting personal data |
| COPPA | `childrens_data` detected | Age verification flows present, or app genre commonly used by children |
| GLBA | `financial_account` detected | Financial services context without explicit account data |
| BIPA | `biometric` detected in Illinois-context app | Biometric-adjacent features (face recognition, voice auth) |
| state_breach_notification | Any PII stored (email + one other identifier) | Any personal data stored without clear US-only exclusion |

`unlikely` should be explicitly emitted for regulations the model considered and ruled out — this shows the assessment was made, not skipped. Omit regulations that are entirely out of scope for the category of app (e.g., FERPA for a fitness tracker with no education context).

## 9. Level 1 DFD construction

The DFD is produced in Step 5.5 of the prompt, after all four domain passes. At that point the model has a complete picture of the codebase and can produce an accurate diagram. The goal is a Level 1 DFD: comprehensive enough to show the system's security structure, concise enough to read in under two minutes.

**The four elements of a Level 1 DFD:**

*External actors* — entities outside the application boundary that exchange data with it. Rendered as rounded rectangles `([Name])`. Differentiate by trust level: unauthenticated visitors, authenticated users, admin users, and inbound third-party services (webhooks, OAuth providers) each get their own actor if their access surface is materially different.

*Processes* — application components that receive, transform, or route data. Rendered as rectangles `[Name]`. Group related handlers into one box: public routes, authenticated routes, admin routes, background workers. Show the system as it is — if the admin panel has no auth, name it plainly and label the data flow accordingly.

*Data stores* — anywhere data persists. Rendered as cylinders `[(Name)]`. Include primary databases, caches, session stores, file/object storage, and message queues when they have distinct data flows.

*Data flows* — labeled arrows connecting elements. Labels describe what moves, not just "request": `-->|"user credentials"|` and `-->|"payment records"|` are good; `-->|"data"|` is not. Inbound flows from actors describe what the actor presents; outbound flows to stores describe what is read or written.

**Trust boundaries** — rendered as `subgraph` blocks. Two or three is usually sufficient: the public internet (all external actors), the application server (all processes), and optionally a data tier (if there is a meaningful network boundary between app and stores).

**Mermaid conventions for this tool:**

```
flowchart LR
    %% External actors: rounded rectangles
    actor_id([Actor Name])

    %% Processes: rectangles
    proc_id[Process Name]

    %% Data stores: cylinders
    store_id[(Store Name)]

    %% Trust boundary: subgraph
    subgraph boundary_id["Boundary Label"]
        ...elements...
    end

    %% Data flows: labeled arrows
    source -->|"data label"| target
    source <-->|"bidirectional"| target
```

Use `flowchart LR` (left-to-right) as the default. Use `flowchart TB` (top-to-bottom) only when the system is tall and narrow (many sequential pipeline steps). Node IDs must be unique, lowercase, with underscores: `users_db`, `admin_panel`, `stripe_webhook`. These IDs are referenced by `dfd_element` on findings — keep them stable and meaningful.

**Simplification principles:**

*Maximum ~15–20 nodes total.* A diagram with 30 nodes is unreadable. When in doubt, group rather than split. "All authenticated API endpoints" is one process box, not twelve.

*Don't show what you can't determine.* If the deployment topology is unknown (no IaC in the repo), don't draw a load balancer that might not exist. Show the application server as one process. Add a note in `dfd.notes` about what was inferred vs. observed.

*Show the system as it is, not as it should be.* If the admin panel has no authentication enforced, the data flow from Admin User → Admin Panel is labeled with what's actually presented (e.g., `-->|"HTTP (no auth enforced)"|`). The DFD is a factual map, not an aspirational one. This is where the diagram delivers genuine insight — the security gap is visible without any annotation.

*External services the app calls out to* appear as external actors, not processes:
- `app_server -->|"payment intent"| stripe([Stripe])` ✓
- Stripe as a process box inside the app server boundary ✗

**What a good Level 1 DFD produces:** A reader who has never seen the codebase can answer — who are the different user types and what do they access? Where does data come in and where does it go? What is stored, and where? Where are the trust boundaries and are there obvious gaps? Individual function calls, variable names, query details, and anything below the level of "which component talks to which component with what data" belong in findings, not in the diagram.

## 10. Order of analysis

The prompt walks the model through the domains in this order. Order matters because some findings depend on context established earlier.

1. **Dependencies first** — fast, mechanical, scoped to lockfiles. Establishes vulnerable-component context for §3 reachability claims.
2. **Secrets & config** — also fast, mostly local-pattern based.
3. **Code-level** — the bulk of the work, requires reasoning about each handler/function/data flow.
4. **Architecture & threat modeling** — needs the full picture, so it goes last. Architectural findings often *consume* findings from the earlier domains as evidence (e.g., "the missing-authz architectural gap is what makes the SQL injection in §3 critical instead of merely high").

The model should not jump back to revise findings from earlier domains as it discovers later context — instead, it cross-references via `related_locations` and notes the connection in `exploitation_path`. This keeps the analysis cleanly sectioned.
