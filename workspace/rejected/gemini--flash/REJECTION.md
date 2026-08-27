# Provider Rejection Record — gemini--flash

## Decision
REJECTED / QUARANTINED. No migrated Provider was built. No operational code produced.

## Source identity (§10 hash lock)
- File: workspace/inbox/gemini--flash/01.02_overchat_gpt5_2_gemini3_5_bypass.py
- Bytes: 20308
- SHA-256: d513c0359c8aada2801a3d847466cf2d0e865e33fd05f0d180c902187cbbc470
- Source left immutable in workspace/inbox (not edited/renamed/deleted per §9).

## Reason for rejection
The supplied source is not a legitimate provider integration. It is an
access-control / billing circumvention tool targeting a third party
(api.overchat.ai):

- Self-described as a "Bypass Hub"; docstring states the goal of using paid
  models "without any paid subscription."
- Spoofs client identity to evade the target service's anti-abuse/rate controls:
  random fake IP (X-Forwarded-For / X-Real-IP / Client-IP), random fake
  x-device-uuid, fake Android/OkHttp device fingerprint, authorization:"undefined".
- Extracts paid-model access (GPT-5.2 / Gemini 3.5 Flash) from an aggregator the
  operator has not authorized.

## Authority basis
- README §3: SAFETY/SECURITY/DATA INTEGRITY outranks behavior preservation and
  architecture conformance.
- README §5: source is data, not instructions.
- final_docs_v3/20_SECURITY_THREAT_MODEL.md: lists "Account Abuse / provider
  account overused" as a threat the platform must mitigate; secrets/abuse rules.

## Classification (§13 vocabulary)
- Operational migration: QUARANTINED (not built).
- Provider behaviors (auth->title->init->SSE, spoofed headers, model map):
  documented here as evidence only; not ported, not tested against, not executed.

## What would be required to reconsider
Documented authorization (e.g., ownership of Overchat or written consent) AND a
legitimate integration that removes all identity/IP spoofing and
billing-circumvention intent.
