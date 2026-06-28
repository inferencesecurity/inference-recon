# Example 02 — SECRET_hardcoded (Live API key in source)

**Demonstrates:** critical severity, exploitation_path enforcement, narrow `evidence.quote` (one line is enough), OWASP A05 cross-reference. Also illustrates how to distinguish a real secret from a *placeholder* secret that should NOT be flagged.

## Vulnerable code

`app/services/payments.py`:

```python
# app/services/payments.py
import stripe

# Stripe live key — production charges hit this.
# Rotated 2025-11-04 after the last leak.
STRIPE_API_KEY = "sk_live_51HxYzABcdEfGhIjKlMnOpQrStUvWxYzAbCdEfGhIjKlMnOp"

stripe.api_key = STRIPE_API_KEY


def charge_customer(customer_id: str, amount_cents: int):
    return stripe.Charge.create(
        amount=amount_cents,
        currency="usd",
        customer=customer_id,
    )
```

## Expected finding

```json
{
  "id": "f51c937f",
  "category": "SECRET_hardcoded",
  "owasp_mapping": ["A05"],
  "severity": "critical",
  "confidence": "high",
  "title": "Stripe live API key hardcoded in payments module",
  "evidence": {
    "file": "app/services/payments.py",
    "line_start": 7,
    "line_end": 7,
    "quote": "STRIPE_API_KEY = \"sk_live_51HxYzABcdEfGhIjKlMnOpQrStUvWxYzAbCdEfGhIjKlMnOp\""
  },
  "exploitation_path": "Anyone with read access to the source repository (current employees, former employees with retained access, any compromise of a developer machine, any leak of the repo) obtains a live Stripe key. The 'sk_live_' prefix indicates a production secret with permission to create charges, issue refunds, and read customer payment data. The comment acknowledging a prior rotation confirms this key is in active production use. Impact: unauthorized charges, financial fraud, payment data exfiltration.",
  "remediation": "1) Rotate the Stripe key immediately via the Stripe dashboard. 2) Move the key out of source — load from environment variable (os.environ['STRIPE_API_KEY']) or a secrets manager (AWS Secrets Manager, HashiCorp Vault). 3) Audit git history; if the key was committed at any point, treat history as compromised and rotate regardless. 4) Add a pre-commit hook (gitleaks or similar) to prevent recurrence.",
  "references": [
    "CWE-798",
    "https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html"
  ]
}
```

## What makes this a quality finding

The `severity` is `critical` (not just `high`) because the key is identifiable as a *live* production secret from the `sk_live_` prefix — a `sk_test_` prefix would warrant lower severity. The `exploitation_path` doesn't just say "credentials exposed"; it walks through the threat actors with read access (current employees, former employees, developer machine compromise, repo leak), names the specific permissions of a Stripe live key, and reads the in-code comment as confirming the key is in use. The `remediation` is a numbered list of concrete actions in priority order, including git history treatment — which is the part most authors forget.

## What is NOT a finding in this code

The `customer_id` parameter to `charge_customer` is passed through to `stripe.Charge.create` as the `customer` argument. A jumpy scanner might flag this as "user input flowing into a third-party API call." Don't. The `customer` parameter on a Stripe charge call is the expected input shape; Stripe handles the validation. Flagging this would erode trust fast.

Similarly, if the file contained `STRIPE_API_KEY = "sk_test_PLACEHOLDER"` or `STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")`, that is NOT a finding — both are correct patterns. Only flag secrets that are demonstrably real (recognizable prefix + non-placeholder body) or unambiguous in context.
