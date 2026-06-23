# Forward Deployed Engineer

**Company:** E2B
**Location:** San Francisco
**Apply:** https://jobs.ashbyhq.com/e2b/a9ddb7bc-9cc7-43d2-8e46-9c8de4666a04
**Ashby Org:** e2b
**Ashby Job ID:** a9ddb7bc-9cc7-43d2-8e46-9c8de4666a04

---

# **About E2B**

E2B is a fast-growing Series A startup with 8-figure revenue. We've raised over $37M since our founding in 2023. Our customers include companies like Microsoft, Perplexity, Hugging Face, Manus, and Groq. We're building the next hyperscaler for AI agents.

# **About the role**

This is our first FDE hire. **You'll define how E2B works with enterprise customers technically** - the deployment playbooks, the integration patterns, the reference architectures. What you build becomes the foundation for the team that follows.

You'll be E2B's technical point of contact for our most important customers - the ones building AI agents that need secure and scalable sandboxes for their AI agents.

Your job is to make these customers successful. That means sitting inside their architecture, understanding their constraints, and doing whatever engineering work it takes to get E2B running in production. Some weeks that's writing a custom sandbox template. Other weeks it's debugging a networking issue in a BYOC deployment, building an integration prototype, or pairing with a customer's engineering team to redesign how they handle sandboxed execution.

You'll work directly with the customer's engineers and our internal engineering team. When you hit a product limitation, you don't just file a ticket - you understand the problem deeply enough to propose a solution, and you have the credibility (because you've been in the codebase) to make the case for it.

# 

## **What you'll do**

- **Integrate E2B into customer stacks.** Write code that connects E2B sandboxes to customer applications - SDK integrations, API wrappers, orchestration logic, CI/CD pipeline hooks. Python, TypeScript, and Go are the languages that matter.

- **Plan and execute BYOC and on-prem deployments.** Many enterprise customers won't use E2B's managed cloud - they need E2B running inside their own AWS/GCP/Azure accounts or on bare-metal infrastructure they control. You'll lead these deployments end-to-end: assess their infrastructure, design the network topology (VPC peering, private endpoints, egress controls), provision compute with IaC, wire up observability, validate isolation, and get it to production. You'll work inside environments you don't own, with security policies you didn't write, alongside platform teams with their own opinions about how things should work.

- **Build custom sandbox templates and environments.** Customers have specific runtime requirements - particular system packages, language versions, pre-loaded models, custom filesystems. You'll build and optimize these.

- **Own the technical success of enterprise deals.** From initial technical discovery through production go-live. You're accountable for the customer being live and happy, not just for a successful demo.

- **Debug hard problems under pressure.** A customer's sandbox is crashing in production. Their UFFD handler is deadlocking. Network egress is being blocked by their firewall rules. You figure it out.

- **Feed signal back to product, sales, and engineering.** You'll see patterns across customers - what's missing, what's broken, what's confusing. You'll write up proposals, contribute to design docs, and sometimes ship fixes yourself.

- **Build repeatable assets.** The integration you build for Customer A should become the reference architecture for customers B through Z. You'll write documentation, create example repos, and codify what works.

- **Navigate enterprise IT environments.** Large customers don't just have engineering teams - they have IT, security, and compliance gatekeepers. You'll work through SSO/SAML integration requirements, deal with MDM-managed developer endpoints (Windows and Mac), troubleshoot corporate proxy and firewall interference, and ensure E2B works within the customer's security posture, not around it.

# **What we're looking for**

- **5+ years of software engineering experience**, with real depth in at least one of: backend systems, infrastructure/platform engineering, or DevOps/SRE. You've shipped and operated production systems, not just written code.

- **Strong proficiency in Python and TypeScript.** Go is a bonus. You'll read and write code in these languages daily - not toy scripts, but integrations, tooling, and debugging production systems.

- **Hands-on Linux and systems knowledge.** You're comfortable with networking (iptables, DNS, overlay networks), process isolation (namespaces, cgroups), systemd, and debugging with strace/tcpdump/perf. You don't need to be a kernel developer, but you need to be able to reason about what's happening below the application layer.

- **Real cloud infrastructure experience.** You've built and operated on AWS, GCP, or Azure - not just used managed services, but configured VPCs, managed IAM, set up private networking (VPC peering, PrivateLink/Private Service Connect, Transit Gateway), debugged routing and DNS, and understood billing. Experience deploying software into someone else's cloud account (BYOC, managed service, or on-prem) is a strong plus. Terraform/Pulumi experience is expected.

- **Understanding of virtualization and isolation models.** You know the difference between container isolation and VM-level isolation, and why it matters for running untrusted code. Familiarity with Firecracker, QEMU, or other VMMs is a significant plus.

- **Enterprise deployment experience.** You've navigated the realities of deploying software into enterprise environments - SSO/SAML/OIDC integration, corporate proxies, MDM-managed endpoints (both Windows and Mac), endpoint security agents that break things, IT approval workflows, and the general friction of getting developer tools running in locked-down environments. You don't need to be an IT admin, but you need to not be surprised when a customer's Zscaler proxy blocks your API calls or their MDM policy prevents local tool installation.

- **Customer-facing communication skills.** You can explain a complex systems issue to a CTO in two sentences and then pair-program the fix with their senior engineer. You don't BS - when you don't know, you say so and go find out.

- **Autonomy and ownership.** You'll often be the only E2B person working with a customer. You need to be able to manage your own time, escalate the right things, and make judgment calls about what to build vs. what to push back on.

- **Excited to work in person from San Francisco** and collaborate directly with the GTM team, CEO, and engineering.

## **Nice-to-have**

- Familiarity with AI agent frameworks (LangChain, CrewAI, Vercel AI SDK)

- Security and compliance background - SOC 2, HIPAA, GDPR conversations with enterprise customers

- Deep familiarity with enterprise identity stacks (Okta, Azure AD/Entra, Google Workspace) and how they interact with developer tooling

- Experience with BYOC / managed-service deployment models - deploying and operating your product inside a customer's cloud account, dealing with their IAM boundaries, network restrictions, and compliance requirements

- On-prem or air-gapped deployment experience - bare metal provisioning, offline package mirrors, working without internet access during setup

- Previous FDE, solutions engineer, or professional services role at a developer tools / infrastructure company (Palantir, Databricks, Vercel, HashiCorp, etc.)

- Contributions to open-source projects

# **What it’s like to work at E2B**

We’re a fast-growing startup with in-person (4 days on-site, 1 day WFH) offices in **San Francisco and Prague, Czech Republic**. We already generate 8-figure revenue and work directly with top-tier AI companies like Perplexity, Hugging Face, and other exciting teams pushing the frontier of AI.

We cover **full healthcare, vision, and dental insurance**, and offer **unlimited PTO**.
