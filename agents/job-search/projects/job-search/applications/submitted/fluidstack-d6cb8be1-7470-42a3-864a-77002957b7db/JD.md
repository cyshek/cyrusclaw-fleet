# Product Manager, Networking

**Company:** Fluidstack
**Location:** San Francisco, CA
**Apply:** https://jobs.ashbyhq.com/fluidstack/d6cb8be1-7470-42a3-864a-77002957b7db
**Ashby Org:** fluidstack
**Ashby Job ID:** d6cb8be1-7470-42a3-864a-77002957b7db

---

# About Fluidstack

We exist to make humanity more free. For most of human history, you farmed or you starved. Technology gave people more time for the things they wanted to do, instead of things they had to do. Powerful AI will be the biggest lever for human choice we've ever built - but only if models are aligned with what humanity actually wants. There are groups building AI who don't share these goals. Whoever deploys frontier compute infrastructure fastest will decide whether AI expands human freedom or shrinks it. 

We're singularly focused on delivering 10 to 100s of GWs of compute faster than anyone else, rethinking every layer of the stack. We acquire power, design and build data centers, and operate them - with teams spanning hardware and software. Speed and scale are our key differentiators. Come be a part of building civilization-scale infrastructure for AI.

**We hire people who care deeply about this problem space. If that is you, please apply!**

**About the Role**

We are hiring a Product Manager to own the tools and systems our team uses to design, deploy, operate, and remediate the networks that run our GPU clusters. That means frontend Ethernet fabrics, backend Ethernet and InfiniBand interconnects, out-of-band management networks, and building management systems. The surface area is wide: BOM generators, configuration generators, digital twins, observability pipelines, and performance profiling tools all sit under this charter.

This is not a role for someone who hands requirements to engineers and waits. You will be the person with the clearest opinion in the room on what needs to be built, why the current state is broken, and what the right architecture looks like. You should be fluent in the underlying technology, having worked hands-on with network gear, streaming telemetry, or large-scale fabric automation at some point in your career. The networking team will trust your judgment because you have earned it technically.

The right candidate has a working mental model of how a 400G spine-leaf fabric is cabled, what gRPC-based telemetry looks like at 10,000 devices, and why config generation is harder than it sounds.

**You Will**

- Own the product roadmap for all internal networking tooling: design automation, provisioning, observability, performance analysis, and incident remediation workflows across frontend, backend, OOB, and BMS networks.

- Drive the strategy and requirements for digital twin tooling that models physical fabric topology, enabling engineers to validate designs, simulate failures, and test config changes before touching production.

- Define and ship BOM generators that produce accurate, version-controlled bills of materials for frontend Ethernet, backend Ethernet, InfiniBand, and OOB networks tied directly to cluster topology specs.

- Own the configuration generation pipeline: translate high-level cluster designs into device-ready configs across switches, routers, and OOB management infrastructure, with correctness guarantees and rollback support.

- Build the observability stack requirements for network telemetry ingestion (gNMI, SNMP, streaming) into dashboards and alerting systems that give operators sub-minute visibility into fabric health and performance degradation.

- Define performance profiling tooling that surfaces InfiniBand and RoCEv2 congestion, all-reduce bottlenecks, and east-west bandwidth saturation at the GPU job level, not just the interface level.

- Work with network engineers and site operations to map the full lifecycle of a network event from detection through remediation, then build the tooling that compresses mean time to resolution.

- Partner with infrastructure and software engineering teams to integrate networking tooling into the broader cluster lifecycle: from site design through rack-and-stack, burn-in, and steady-state operations.

- Define the data model and schema standards that sit underneath all networking tools, ensuring BOM data, topology data, telemetry data, and config state are coherent and queryable across systems.

- Conduct working sessions with network engineers, site leads, and operations staff to identify the highest-friction workflows, then prioritize ruthlessly based on operational impact.

**Basic Qualifications**

- 5+ years of product management experience with at least 3 years focused on infrastructure, networking, or platform tooling.

- Direct working knowledge of data center networking technologies: spine-leaf topology, EVPN/VXLAN, BGP, 400G/800G Ethernet, and high-radix switch platforms from vendors such as Arista, Cisco Nexus, or Nvidia Spectrum.

- Hands-on familiarity with high-performance interconnects: InfiniBand (HDR/NDR), RoCEv2, and the operational realities of running large-scale RDMA fabrics under AI training workloads.

- Working knowledge of network telemetry protocols and frameworks: gNMI/gRPC streaming, SNMP, OpenConfig, and at least one observability stack built on top of them (Prometheus, InfluxDB, Grafana, or equivalent).

- Experience shipping internal tooling or developer-facing platform products, not just external customer-facing products.

- Ability to write detailed technical specifications that engineering teams can execute against without follow-up clarification.

- Demonstrated track record of reducing operational toil through automation: config generation, provisioning workflows, or similar.

**Preferred Qualifications**

- Experience at a hyperscaler, neocloud, or large-scale GPU infrastructure company where you owned networking tooling end-to-end (AWS, Azure, GCP, Oracle, CoreWeave, Lambda, or equivalent).

- Prior background as a network engineer or network automation engineer before moving into product: you have personally written Ansible playbooks, Nornir scripts, YANG models, or equivalent configuration automation.

- Familiarity with digital twin or network simulation frameworks: emulated environments built on tools like GNS3, EVE-NG, Containerlab, or proprietary fabric simulation systems.

- Experience defining or operating out-of-band management networks: IPMI/BMC, console servers, and the tooling used to reach devices when the in-band network is down.

- Understanding of BMS integration patterns in hyperscale facilities: BACnet, Modbus, SNMP-based BMS interfaces, and the data normalization challenges that come with multi-vendor BMS environments.

- Exposure to AI/ML workload network requirements: collective communication libraries (NCCL, RCCL), all-reduce topologies, and how fabric decisions impact training throughput and model FLOP utilization.

- Familiarity with network source-of-truth and IPAM systems: NetBox, Nautobot, or internal equivalents used to drive automation.

We are committed to pay equity and transparency.

Fluidstack is an Equal Employment Opportunity Employer. All qualified applicants will receive consideration for employment without regard to race, color, religion, sex, national origin, sexual orientation, gender identity, disability and protected veterans’ status, or any other characteristic protected by law. Fluidstack will consider for employment qualified applicants with arrest and conviction records pursuant to applicable law.

*You will receive a confirmation email once your application has successfully been accepted. If there is an error with your submission and you **did not** receive a confirmation email, please email careers@fluidstack.io with your resume/CV, the role you've applied for, and the date you submitted your application-- someone from our recruiting team will be in touch. *
