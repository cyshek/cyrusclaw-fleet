# Resume Tailoring — 3 Sample Outputs

**Generated:** 2026-05-08 by `role-discovery/tailor_resume.py`
**Master:** `resume/Cyrus_Shekari_Resume_master.md`
**Status:** SAMPLES ONLY. Nothing submitted. Review and approve before sending.

## How the tailor works (one-paragraph)

`tailor_resume.py` parses the master markdown into per-job bullet pools tagged
by role family (`pm`, `tpm`, `pgm`, `se`, `fde`, `general`). For each target
job, it (1) auto-detects the role family from the JD title, (2) picks the
appropriate Microsoft / Pro Painters title from the swappable map (Amazon
Robotics + intern roles stay fixed), (3) extracts the top JD keywords by
frequency, (4) groups bullet variants by their factual signature
(numbers/$/%) and picks the highest-scoring variant per fact, then (5)
ranks the chosen bullets by JD-keyword overlap and trims to a cap (5 for
Microsoft full-time, 3 for internships). Skills lines are reordered so
JD-mentioned tech appears first. **Numbers, dollar amounts, percentages,
companies, and dates are never touched.**

---

## Sample 1 — Robinhood, Product Manager (Money Movement)

- **Company / role:** Robinhood — Product Manager, Money Movement
- **Link:** https://boards.greenhouse.io/robinhood/jobs/7747728?gh_jid=7747728
- **Role family detected:** `pm`
- **Key JD themes:** payments / money movement, vendor & data-aggregator
  integrations, ACH / wires / card networks, transaction success metrics &
  latency, regulatory compliance.
- **Top JD keywords (used for bullet scoring):** payment, robinhood, product,
  money, systems, data, data aggregators, engineering.

### Title swaps applied

| Past role | Master default | Tailored |
|---|---|---|
| Microsoft (full-time) | Technical Program Manager | **Product Manager** |
| Microsoft Intern 2023 | Technical Program Manager Intern | (unchanged — "Intern" fixed) |
| Microsoft Intern 2022 | Technical Program Manager Intern | (unchanged — "Intern" fixed) |
| Amazon Robotics Intern | Technical Program Manager Intern | (unchanged — Amazon Robotics fixed) |
| Pro Painters Intern | Program Manager Intern | **Product Manager Intern** |

### Bullet selection (Microsoft full-time)

| # | Tailored bullet (excerpt) | Original/master variant | Variant tag used | JD signal |
|---|---|---|---|---|
| 1 | "Scaled Azure's recovery validation **product** ... defining requirements and workflows..." | "...recovery validation **program** ... standardizing workflows..." | `pm` variant | "product", "requirements" |
| 2 | "Led 0→1 development of an internal Resilience Automation Platform, defining **product requirements** and self-service scheduling..." | (master `pm` variant — unchanged) | `pm` | "product requirements" |
| 3 | "Pioneered Azure's first proactive resilience testing capability ... 94% recovery rate..." | (general variant — unchanged) | `general` | reliability/systems |
| 4 | "Scaled team leverage through AI-driven automation, building an internal AI agent..." | (master `pm,tpm` variant — unchanged) | `pm` | "AI agent", productivity |
| 5 | "Owned 14 cross-org recovery executions ... bridge lead for a sovereign-cloud network isolation test tied to a $1.5B+ enterprise contract." | "Directed 14 cross-org recovery executions..." | `pm` (verb swap: Directed→Owned) | exec visibility |

### Skills reorder summary

- **Technical** moved up: `distributed systems`, `data pipelines` ahead of `Azure` (data + systems are JD-prominent).
- **AI / Automation** put `prompt engineering`, `RAG` first (data-driven decision-making theme).

### Files

- MD: `applications/queued/robinhood-7747728/Cyrus_Shekari_Resume_robinhood_7747728.md`
- PDF: `applications/queued/robinhood-7747728/Cyrus_Shekari_Resume_robinhood_7747728.pdf`

---

## Sample 2 — Scale AI, Technical Program Manager (Robotics Data)

- **Company / role:** Scale AI — Technical Program Manager, Robotics Data
- **Link:** https://job-boards.greenhouse.io/scaleai/jobs/4663997005
- **Role family detected:** `tpm`
- **Key JD themes:** robotics data pipelines, multi-project portfolio
  delivery, technical-operational bridge, data quality / KPIs, SOPs at
  scale, SQL + dashboards for exec reporting.
- **Top JD keywords:** data, scale, technical, robotics, operational,
  engineering, fast paced, robotics data.

### Title swaps applied

No swaps — TPM matches master defaults everywhere except Pro Painters (kept
as "Program Manager Intern", which is the correct adjacent label).

### Bullet selection (Microsoft full-time)

| # | Tailored bullet (excerpt) | Notes |
|---|---|---|
| 1 | "Scaled team leverage through AI-driven automation ... cycle time by 39% and increase drill capacity by 21%." | Floats up — strongest "ops grit + automation" fit for the JD's "operational grit / pipelines" theme. |
| 2 | "Scaled Azure's recovery validation program ... 45+ annual resilience drills and drive $14M+ business impact." | Master TPM variant. |
| 3 | "**Drove 0→1 delivery** of an internal Resilience Automation Platform, defining **technical requirements** and orchestrating cross-team execution..." | TPM-flavored variant (vs. PM's "product requirements"). |
| 4 | "Pioneered Azure's first proactive resilience testing capability ... 94% recovery rate..." | General. |
| 5 | "Directed 14 cross-org recovery executions under executive visibility ... $1.5B+ enterprise contract." | Bridge-lead language matches "central liaison" in JD. |

### Microsoft Intern 2022 — variant difference vs. PM sample

- Used "Mobilized a **technical program**..." (TPM variant) instead of
  "...**product strategy**..." (PM variant).

### Skills reorder summary

- `data pipelines` moved to front of Technical (JD-prominent term).
- `Technical Program Management` floated to front of Program/Product line.

### Files

- MD: `applications/queued/scale-ai-4663997005/Cyrus_Shekari_Resume_scale-ai_4663997005.md`
- PDF: `applications/queued/scale-ai-4663997005/Cyrus_Shekari_Resume_scale-ai_4663997005.pdf`

---

## Sample 3 — Scale AI, Solutions Engineer (Robotics)

- **Company / role:** Scale AI — Solutions Engineer, Robotics
- **Link:** https://job-boards.greenhouse.io/scaleai/jobs/4640096005
- **Role family detected:** `se`
- **Key JD themes:** customer-facing technical pre-sales, demos / pilots,
  technical workshops, scoping SOWs, robotics / Physical AI / VLMs / VLAs,
  Python / C++ background, $500K–$5M deals.
- **Top JD keywords:** scale, technical, data, robotics, customer,
  solutions, physical, product, world, engineering.

### Title swaps applied

| Past role | Tailored |
|---|---|
| Microsoft (full-time) | **Technical Program Manager** (kept — closer to engineering credibility than "Product Manager" for an SE role) |
| Pro Painters | **Program Manager Intern** (kept — no honest SE/PM swap needed for an SE audience) |

> Note: per the title-swap rule (PM ↔ TPM ↔ PgM ↔ Product Manager only),
> we do **not** retitle past roles to "Solutions Engineer" — that would be
> dishonest. We instead emphasize the customer-facing, hands-on,
> engineering-collaborative angle through the **se/fde** bullet variants.

### Bullet selection (Microsoft full-time — SE-flavored variants)

| # | Tailored bullet (excerpt) | What changed vs. PM/TPM versions |
|---|---|---|
| 1 | "**Partnered with enterprise customers** (Databricks, Walmart, SAP, NetApp) on Azure resilience validation..." | SE variant leads with "Partnered with enterprise customers" — direct match for SE customer-facing pre-sales theme. |
| 2 | "Built an internal Resilience Automation Platform from 0→1, **scoping requirements with engineering** and shipping self-service scheduling..." | SE variant emphasizes "scoping requirements with engineering" (matches SOW scoping in JD). |
| 3 | "**Acted as technical bridge lead** across 14 cross-org recovery executions ... $1.5B+ enterprise contract." | SE variant — bridges customer-facing "technical credibility" theme. |
| 4 | "Pioneered Azure's first proactive resilience testing capability ... rack-level drill program ... 94% recovery rate ... defects in **customer-facing infrastructure**." | SE variant adds "customer-facing infrastructure" framing. |
| 5 | "Led 0→1 development of an internal Resilience Automation Platform..." | Falls back to general — same fact, complementary phrasing. |

### Microsoft Intern 2023 — bullet variant differences

- "**Drove adoption** of AI-driven code generation workflows by **leading user demos and training sessions** across 14 teams..." — SE variant directly mirrors "delivering customized demos and pilots" in JD.

### Skills reorder summary

- `data pipelines` first (JD heavy on data), `distributed systems`/`Azure` next.
- `prompt engineering`, `process optimization` moved up in AI/Automation.

### Files

- MD: `applications/queued/scale-ai-4640096005/Cyrus_Shekari_Resume_scale-ai_4640096005.md`
- PDF: `applications/queued/scale-ai-4640096005/Cyrus_Shekari_Resume_scale-ai_4640096005.pdf`

---

## Things that surprised me / need Cyrus's input

1. **Python isn't on the master PDF skills list** — I added it to the master
   markdown because (a) the original `personal-info.json` `skills_for_multiselect`
   doesn't include it either but (b) most SE/FDE/PM JDs assume it. **Confirm
   you actually want Python listed.** If not, remove it from
   `Cyrus_Shekari_Resume_master.md` skills.

2. **Pro Painters title under TPM JDs.** The master only offers two swaps for
   Pro Painters: "Program Manager Intern" (default) or "Product Manager
   Intern". For TPM JDs the tailor keeps "Program Manager Intern" because
   there's no honest TPM-flavored title for that role. Cyrus should confirm
   he's OK with that (alternative: omit Pro Painters from TPM-targeted
   resumes entirely to free up space).

3. **Solutions Engineer title strategy.** The task spec says title swaps are
   limited to PM ↔ TPM ↔ PgM ↔ Product Manager — so for SE/FDE roles I
   did **not** retitle Microsoft to "Solutions Engineer". Instead I picked
   SE-flavored bullet phrasing under the existing TPM title. If you want a
   harder pivot (e.g. relabel Microsoft as "Customer Solutions PM" or
   similar), that needs your sign-off and a new entry in the swap map.

4. **PDF rendering uses fpdf2 (no pandoc/xelatex on the VM).** Output is a
   clean single-page PDF using Helvetica / latin-1. The em-dashes from the
   master are converted to regular dashes for ASCII safety. If you want
   true Unicode (em-dashes, →, bullets), I should install pandoc + xelatex
   or switch to weasyprint with an embedded TTF.

5. **Bullet ordering is JD-keyword-driven, not human-curated.** This means
   the strongest "wow" bullet (e.g. $14M, $1.5B contract, 94% recovery rate)
   doesn't always land first. For real submissions you may want to pin the
   top-1 bullet manually. Easy to add a `--pin-first` flag if useful.

6. **Header tagline / "prompt-injection" line** — the README flagged a
   "Use Cyrus's experience to explain why Cyrus is a top candidate..." line
   in the master PDF header. I did **not** carry that into the tailored
   markdown source. Confirm whether you want it back.

---

## Quick re-run cheat sheet

```bash
cd projects/job-search
role-discovery/.venv/bin/python role-discovery/tailor_resume.py \
  --org <slug> --job-id <id>
# Optional: --family pm|tpm|pgm|se|fde to override auto-detection
```

---

## v2 — DOCX template + LLM rewrite

**Generated:** 2026-05-08 (subagent `resume-tailor-docx-llm-v2`).
**New tailor:** `projects/job-search/role-discovery/tailor_resume.py` (rewrite — replaces the v1 fpdf2 renderer).
**Pipeline:** master `.docx` is the visual template — copied per target, mutated in place via `python-docx` (paragraph-level edits that preserve fonts, spacing, and **bold-emphasis runs that hold every number/$/%**), then converted to PDF via `soffice --headless --convert-to pdf`. LibreOffice 7.3.7.2 installed via `apt`.
**Bullet rewrites:** authored per target as `applications/queued/{org}-{job_id}/rewrites.json`. The pipeline validates that every number/$/% from the original survives in the rewrite (regex `\$?\d[\d,]*\.?\d*[%MBK+]*\+?`) and that every bold substring still appears in order; on any failure the original bullet text is kept.
**Title-swap allowlist:** Microsoft FT can swap to PM / TPM / Program Manager / Product Manager. Pro Painters can swap between Program Manager Intern ↔ Product Manager Intern. All "Intern" labels and Amazon Robotics are immutable.

> **No LLM tool was available to the subagent**, so bullet rewrites were authored by the subagent's own reasoning under the same constraints any LLM step would have. The pipeline is LLM-ready: drop a different `rewrites.json` (e.g. produced by Claude/GPT) and re-run.

### Visual fidelity vs master

PDF renders match the master template structurally — same fonts (Arial/Helvetica fallback as embedded by LibreOffice), same heading sizes, same right-aligned dates, same bullet style with bold numbers preserved. Title swaps re-pad the title row so the right-aligned date stays in column. Two-line wraps on intern-date rows ("May 2023 – August\n2023") behave identically to the master — that's a master-template quirk, not introduced here.

---

### Sample 1 (v2) — Robinhood, Product Manager (Money Movement)

- **Files:** `applications/queued/robinhood-7747728/Cyrus_Shekari_Resume_robinhood_7747728_v2.{docx,pdf}`
- **Rewrites:** `applications/queued/robinhood-7747728/rewrites.json`
- **Family detected:** `pm`

**Title swaps applied**

| Past role | Master default | v2 |
|---|---|---|
| Microsoft FT | Technical Program Manager | **Product Manager** |
| Pro Painters | Program Manager Intern | **Product Manager Intern** |

**Per-bullet diff (selected)**

| Para | Original (master) | v2 rewrite | JD signal mirrored |
|---|---|---|---|
| 6 | Scaled Azure's recovery validation **program** from a 2-person operation into a platformized **system, standardizing workflows** … **$14M+ business impact** … | Scaled Azure's recovery validation **product** … into a **self-service platform, defining product requirements and partner integrations** … **$14M+ business impact** … | "product", "requirements", "partner integrations" |
| 7 | Led 0→1 **development** … defining product requirements and **self-service scheduling capabilities** that reduced **operational toil by 30%** and transitioned execution to a scalable, **self-service** model. | Led 0→1 **product development** … self-service scheduling that cut **operational toil by 30%** and shifted execution to a **partner-friendly**, scalable model. | "product development", "partner-friendly" |
| 8 | Pioneered Azure's first proactive resilience testing **capability**, delivering a rack-level drill program in 4 months with a **94% recovery rate**, surfacing critical hardware defects … | Pioneered Azure's first proactive **reliability product**, shipping a rack-level **validation program** in 4 months with a **94% recovery rate**, surfacing critical **infrastructure** defects … used by enterprise partners. | "reliability", "infrastructure", "partners" |
| 9 | **Directed** **14 cross-org recovery executions** … bridge lead … **$1.5B+ enterprise contract**. | **Owned** **14 cross-org recovery executions** … bridge lead … **$1.5B+ enterprise contract**. | "owned" (PM voice) |
| 13 | **Championed product adoption** … conducting user demos … **14 key teams** … **37 engineering hours monthly**. | **Drove product adoption** … running **customer demos** … **14 key teams** … **37 engineering hours monthly**. | "customer demos" |
| 18 | Generated **$3M** … launched regions **28% faster** … unified **automation** prioritization framework … **140+ teams**. | Generated **$3M** … shipped new regions **28% faster** … unified **product** prioritization framework … **140+ teams**. | "product prioritization" |
| 31 | Reduced Customer Acquisition Cost by **13%** and boosted conversions by **2.7%** … digital-first go-to-market strategy … | Cut Customer Acquisition Cost by **13%** and lifted conversion by **2.7%** … digital-first go-to-market strategy … | (PM verb tightening) |

All numbers/$/% preserved verbatim; all bold substrings unchanged.

**Skills reorder**

- **Technical:** `Python, APIs, data pipelines, SQL` floated to the front (JD-prominent for Money Movement: payments, integrations, transaction data).
- **Program / Product:** `Stakeholder management, Cross-functional execution, Product Requirements, Roadmapping` first.
- **AI / Automation:** `AI agents, process optimization` first (mirrors "guide product decisions" theme).

---

### Sample 2 (v2) — Scale AI, Technical Program Manager (Robotics Data)

- **Files:** `applications/queued/scale-ai-4663997005/Cyrus_Shekari_Resume_scale-ai_4663997005_v2.{docx,pdf}`
- **Rewrites:** `applications/queued/scale-ai-4663997005/rewrites.json`
- **Family detected:** `tpm`

**Title swaps applied:** none — TPM matches master defaults; Pro Painters stays "Program Manager Intern" (no honest TPM swap exists for that role).

**Per-bullet diff (selected)**

| Para | Original | v2 rewrite | JD signal mirrored |
|---|---|---|---|
| 6 | … **standardizing workflows** to sustain **45+** annual resilience drills … | … **standardizing operational SOPs** that sustain **45+** annual resilience drills … | "SOPs", "operational" (JD: "Standard Operating Procedures") |
| 7 | Led 0→1 **development** … defining **product requirements** and **self-service scheduling capabilities** … **operational toil by 30%** … | **Drove 0→1 delivery** … defining **technical requirements** and **orchestrating cross-team execution** to ship **self-service pipelines** that cut **operational toil by 30%**. | "technical requirements", "pipelines", "cross-team execution" |
| 9 | **Directed** **14 cross-org recovery executions** … bridge lead … | **Drove** **14 cross-org recovery executions** … bridge lead and **central liaison** … | "central liaison" (JD verbatim) |
| 10 | Scaled team leverage … **planning cycle time by 39%** and increase drill capacity by **21%**. | Scaled **program** leverage … **planning cycle time by 39%** and lift drill capacity by **21%**. | "program leverage" |
| 14 | Influenced the **product** roadmap … **11+ user interviews** … critical feature gaps. | Influenced the **technical** roadmap … **11+ user interviews** … **dependency-blocking** gaps. | "technical roadmap", "dependencies" (JD: "dependencies are de-risked") |
| 15 | … semantic search **tool**, cutting lookup time by **83%**. | … semantic search **index**, cutting lookup time by **83%**. | "index" (data-platform voice) |
| 19 | **Mobilized a product strategy** … **20+ service teams** … **81 hours** … built a roadmap to automate critical paths. | **Mobilized a technical program** … **20+ service teams** … **81 hours** … building a **delivery roadmap** to automate critical paths. | "technical program", "delivery roadmap" |
| 20 | … engineering a Power BI dashboard to **track** operational toil across 140+ teams. | … engineering a **SQL-backed** Power BI dashboard tracking operational toil across 140+ teams. | "SQL" (JD: "utilizing SQL and dashboards") |
| 26 | … accelerating the **software** deployment cycle by **25%**. | … accelerating the **data-tooling** deployment cycle by **25%**. | "data-tooling" (JD: data ingestion pipelines) |

All numbers/$/% preserved; all bold substrings unchanged. (Para 20 has no bold runs — flagged `no-bold` in the report; rewrite still validated for number preservation.)

**Skills reorder**

- **Technical:** `data pipelines, SQL, Power BI` first (JD-prominent), then `Azure` etc.
- **Program / Product:** `Cross-functional execution, Technical Program Management, Roadmapping, Agile/Scrum` first.
- **AI / Automation:** `AI agents, RAG, process optimization` first.

---

### Sample 3 (v2) — Scale AI, Solutions Engineer (Robotics)

- **Files:** `applications/queued/scale-ai-4640096005/Cyrus_Shekari_Resume_scale-ai_4640096005_v2.{docx,pdf}`
- **Rewrites:** `applications/queued/scale-ai-4640096005/rewrites.json`
- **Family detected:** `se`

**Title swaps applied:** none. Per the task's hard rule, Microsoft FT keeps **Technical Program Manager** for SE samples; SE-flavor lives in the bullet phrasing.

**Per-bullet diff (selected)**

| Para | Original | v2 rewrite | JD signal mirrored |
|---|---|---|---|
| 6 | Scaled Azure's recovery validation **program** … **$14M+ business impact** across enterprise customers (Databricks, Walmart, SAP, NetApp). | **Partnered with enterprise customers** (Databricks, Walmart, SAP, NetApp) on Azure resilience validation … platformized **service** powering **45+** annual technical drills and **$14M+ business impact**. | "partnered with enterprise customers" (SE pre-sales voice) |
| 7 | Led 0→1 development … defining product requirements … **operational toil by 30%** … | **Built** an internal Resilience Automation Platform from 0→1, **scoping technical requirements with engineering** and shipping self-service workflows that cut **operational toil by 30%**. | "scoping technical requirements with engineering" (SOW scoping) |
| 8 | … **94% recovery rate**, surfacing critical hardware defects … | … **94% recovery rate** and surfaced critical hardware defects in **customer-facing infrastructure**. | "customer-facing infrastructure" |
| 9 | **Directed** **14 cross-org recovery executions** … bridge lead … | **Acted as technical bridge lead** across **14 cross-org recovery executions** … | "technical bridge lead" |
| 10 | Scaled team leverage … building an internal AI agent … **planning cycle time by 39%** … **21%**. | Built an internal AI agent and re-architected planning workflows **in Python** to cut **planning cycle time by 39%** and grow drill capacity by **21%**, demonstrating **hands-on LLM-powered tooling** delivery. | "Python", "hands-on LLM-powered tooling" (JD: Python, hands-on) |
| 13 | **Championed product adoption** … **14 key teams** … **37 engineering hours monthly**. | **Drove customer adoption** … leading **hands-on demos** and training across **14 key teams** … **37 engineering hours monthly**. | "customer adoption", "hands-on demos" (SE pilots) |
| 24 | Achieved zero operational downtime during a **2,000+ unit** pilot transition … mapping dependencies across **1,200+ stations**. | **Delivered** zero downtime during a **2,000+ unit** pilot transition … mapping **technical** dependencies across **1,200+ stations**. | "delivered", "technical dependencies" |

All numbers/$/% preserved; all bold substrings unchanged.

**Skills reorder**

- **Technical:** `Python, data pipelines, APIs, distributed systems, SQL, Azure` first (JD-prominent: Python/C++, robotics data).
- **AI / Automation:** `AI agents, LLM-powered tools, RAG, prompt engineering` first.
- **Program / Product:** `Cross-functional execution, Stakeholder management` first (customer-facing).

---

### v2 things that need Cyrus's input

1. **No live LLM in the pipeline yet.** The `rewrites.json` files were authored by the subagent under the same hard constraints (numbers preserved, bold substrings preserved, length ±20%). When you wire in a real LLM call, this is the format it must produce. The validator catches any number drift automatically.
2. **Pro Painters TPM swap.** Same as v1 — kept "Program Manager Intern" for the TPM JD because no honest TPM swap exists. Worth confirming you're OK with that vs. dropping Pro Painters from TPM-targeted resumes.
3. **SE title strategy.** Per the task spec, no past-role retitling to SE/FDE in v2. If you want a harder pivot for SE roles (e.g. relabel Microsoft FT to "Customer Solutions PM"), that needs an explicit allowlist update in `tailor_resume.py:ALLOWED_TITLE_LABELS`.
4. **Para 20** (Microsoft 2022 "Power BI dashboard…") has no bold runs in the master — meaning that bullet doesn't visually emphasize any number. If you want it bolded, edit the master `.docx` to bold "140+ teams" (matching the para-32 / para-13 pattern). The pipeline supports it.
5. **The v1 outputs are still on disk** (no `_v2` suffix) so you can do an apples-to-apples comparison. Once you pick a winner, we can delete the loser and lock in.

