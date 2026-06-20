# Coach Notes — Partner Technology Solutions Engineer @ Datadog (NYC)

_Prep companion to `Datadog_PTSE_Interview_Prep_Guide.docx`. Honest read, per Cyrus's
"honesty over overselling" preference._

---

## The frame that wins this interview
This role is a **technical-consultant / developer-enablement** role, not a build-from-scratch SWE
role. Datadog wants someone who can (a) speak observability fluently, (b) consult external
developers through the integration lifecycle, and (c) feed partner friction back to Product/Eng.
**Cyrus's whole story already maps to (c) and the "turn complex engineering into self-service"
thesis** — lean on that hard. His differentiator vs. a pure support engineer is that he's operated
as a **platform/program owner who drove adoption and influenced roadmaps**, which is exactly the
"identify IDP friction, partner with Product/Eng" half of the JD.

## Strongest angles (lead with these)
1. **He is genuinely an observability native.** In his recovery work, telemetry *was* the product —
   metrics/logs/traces were how he proved recovery and surfaced latent hardware defects. This makes
   the three-pillars / OTel answers credible, not memorized. Play this up.
2. **Developer-experience + adoption is his signature.** The GDOT story (influence w/o authority,
   roadmap influence, onboarding scaffolding) and the self-service platform story (A/B-tested UX,
   help copilots, 35% friction cut) are *perfect* analogies for partner enablement and IDP feedback.
3. **He already uses + critiques AI coding tools.** JD explicitly lists this as a bonus. He built the
   drill-automation agent with GitHub Copilot — frame it as "validate/refine AI output, don't trust
   blindly," which is the exact bonus skill and relevant to reviewing partners' AI-assisted code.
4. **Cross-functional technical translation.** He's been the bridge between platform eng, availability
   teams, and service owners. A Partner TSE is the bridge between Datadog and external devs — same
   muscle, different audience.

## Story → likely-question map (all anchored on his existing 7; nothing invented)
| Likely question | Anchor story (Section 2) | Reframe |
|---|---|---|
| Frustrated partner/customer | **Q7** (frustrated customer) | internal service team → external partner-dev |
| Influence without authority / drive tool adoption | **Q6** (GDOT) | operators → partner ecosystem / IDP best practices |
| Drive platform / self-service adoption | **Q4** (automation platform) | internal platform → developer enablement & docs |
| Mid-flight technical pivot w/ stakeholders | **Q2** (Service Healing pivot) | drill design → partner integration architecture review |
| Most ambiguous 0-to-1 thing you owned | **Q1** (proactive testing incubation) | blank-page partner architectures |
| Hard prioritization trade-off | **Q5** (MVP scope) | help partner sequence to a rubric-passing MVP |
| Senior/exec urgent request | **Section 3** framework | reuse as-is |

## GAPS / risks to shore up (be honest in the room)
1. **Hands-on integration/SDK depth is his thinnest area.** He has NOT personally built a Datadog
   Agent check, written a `ddev`-scaffolded integration, implemented an OAuth server, or shipped a
   Marketplace tile. If they go deep hands-on ("walk me through writing an agent check / debugging a
   log pipeline you built"), he's reasoning from strong adjacent knowledge, not lived experience.
   **Mitigation:** the guide's B-bucket answers are framed as "how I'd approach it" + transferable
   real examples, and explicitly say "I've reasoned about this, not implemented X from scratch."
   That honesty matches Datadog's stated values (pragmatism, honesty, simplicity) and is safer than
   bluffing. **Highest-leverage prep before the interview:** spend an hour in the Datadog Integration
   Developer Platform docs + skim the `integrations-extras` repo so he can speak concretely about
   `ddev`, the scaffolding, and a real tile's structure. Even a tiny hands-on poke would convert this
   gap into a strength.
2. **Coding language depth (Python/Go).** JD wants proficiency in at least one (Python/Go preferred).
   His background is TPM-leaning; he's used Python-adjacent tooling and AI codegen, but if there's a
   live coding or "write this in Python" screen, that's a real bar. **Mitigation:** confirm with the
   recruiter whether there's a coding exercise; if yes, brush up Python basics (scripting, REST calls
   with `requests`, parsing JSON) — that's the exact shape of integration glue code.
3. **"Support-engineering" reflexes (Zendesk/Slack triage cadence).** He's done escalations and
   incident bridges (strong), but day-to-day ticket-queue support is a different rhythm. Likely fine,
   but if asked about handling a high-volume queue, anchor on the escalation-handling instinct from
   Q7 + the Section 3 prioritization framework rather than claiming queue experience he doesn't have.

## Quick-study cheat list (internalize cold)
- **3 pillars:** metrics = *that* it's wrong; logs = *what* happened; traces = *where* (across
  services). Monitoring = reactive/known signals; observability = proactive/ask *why*.
- **OTel:** CNCF, vendor-neutral; API (decoupled, no-op without SDK) / SDK (sampling, batching) /
  OTLP (de-facto wire format) / semantic conventions (consistent attr names) / Collector
  (receiver → processor → exporter, can fan out).
- **Integration types:** Agent-based (runs on customer infra, Python `check`, metrics/events/logs;
  traces via SDK) · Auth/crawler (Datadog pulls via API w/ creds — AWS/Azure/Slack) · Library
  (Datadog API + client libs in-app). JD's "agent-based vs API-based" = on-host collect vs REST send
  (API-based needs **OAuth 2.0**).
- **Official-integration requirements:** ≥1 telemetry type + OOTB dashboard + tile images;
  API-based → OAuth 2.0; logs → log pipeline; metrics → monitor template.
- **Lifecycle:** apply to Datadog Partner Network (Technology Partner track) → dev sandbox → build on
  the **IDP** (`ddev`, fork `integrations-extras` for OOTB or `DataDog/marketplace` repo for paid) →
  test in sandbox → submit for review vs. **Quality Rubric** → Datadog publishes (Integrations page
  or **Marketplace**, which has managed billing + 14-day trials).

## Sources (researched 2026-06-07)
1. Datadog PTSE job description — Greenhouse ID 7961297 (saved JD in bundle/).
2. Datadog product & platform overview — datadoghq.com/product.
3. "What Is Observability?" — Datadog Knowledge Center (three pillars; monitoring vs observability).
4. "OpenTelemetry Overview" — Datadog Knowledge Center (API/SDK/OTLP/conventions/Collector).
5. Datadog Docs — "Introduction to Integrations" (getting_started/integrations): agent/crawler/library
   types, integrations-core vs integrations-extras, API & app keys, conf.yaml setup.
6. Datadog Docs — "Datadog Integrations" / Integration Developer Platform (extend/integrations):
   integration requirements, OAuth/log-pipeline/monitor-template gates, DPN → sandbox → IDP →
   submit-for-review lifecycle, OOTB vs Marketplace.
7. Datadog Docs — "Create an Agent-based Integration" (extend/integrations/agent_integration):
   `ddev` tooling, scaffolding, integrations-extras vs DataDog/marketplace repos, Python `check`,
   metrics/events/logs (traces via SDK).
8. "Expand your monitoring reach with the Datadog Marketplace" — datadoghq.com/blog/datadog-marketplace
   (Marketplace launch, managed billing, 14-day trials, Datadog Partner Network).
