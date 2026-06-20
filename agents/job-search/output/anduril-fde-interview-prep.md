================================================================================
ANDURIL — FORWARD DEPLOYED ENGINEER (MISSION AUTONOMY) — INTERVIEW PREP
Internal title: Technical Operations Engineer | Costa Mesa, CA (on-site, no remote)
Prepared for: Cyrus Shekari
Grounded in: real resume + May 2026 Microsoft Connect performance review
================================================================================

HOW TO USE THIS DOC
- Each question has a "BEATS" line (your fast cheat-sheet trigger) followed by the
  full word-for-word SCRIPT. For day-of review, just read the BEATS lines.
- Learn the STORIES, not the exact words. Reciting = obvious. Sound like you lived it
  (you did), not like a teleprompter.
- Honesty frame: you're a TPM/program person moving toward the hardware/software
  field-ops seam. Sell transferable infra + ownership HARD, but NEVER claim production
  K8s / field-SRE / high-voltage expertise you don't have. Calibrated honesty is a
  STRENGTH here — it reads as trustworthy and they'll respect it.

KEY REAL FACTS YOU CAN CITE (all from the perf review — verifiable):
- Azure's FIRST proactive drill — led incubation -> first end-to-end exec in 4 months.
  ~94% autonomous recovery (15/16 nodes). Surfaced a latent HARDWARE defect that
  wouldn't have shown up until a real outage.
- Owned 4 drills end-to-end; contributed to 6 of 14 scoped drills vs annual KPIs.
- Led Sovereign BLEU network-isolation drill ($1.5B contract) — ran the MAIN BRIDGE
  mid-execution under VP-level visibility.
- Azure NetApp Files drill: failover latency >20 min -> ~2-3 min.
- Built rack->node + node->service observability mapping (w/ Altus engineers).
- Built a Copilot Studio AI agent from the drill playbook -> team self-serves drill
  steps without expert support. Shipped 3 newsletters (~10k readers).
- Cut manual toil 60h -> 53h in 4 months; owner of the manual-toil KPI.
- Growth arc (manager's words): needed close guidance -> independently owned scoped
  drills end-to-end, planning through execution.
- Setback/lesson: FcShell workaround would've triggered Service Healing -> VM migration
  -> data loss; caught it w/ Avail Platform + DMS, pivoted mid-flight (disabled Anvil
  Recovery) to execute safely. Lesson: validate assumptions early w/ partner teams.


################################################################################
#  SECTION 1 — THE 5 CORE QUESTIONS
################################################################################

================================================================================
Q1 — "TELL ME ABOUT YOURSELF" / WALK ME THROUGH YOUR BACKGROUND
================================================================================
BEATS: CS + math minor -> TPM Microsoft, Azure reliability (make platform recover when
   HW fails) -> first proactive drill, concept->live 4mo, 94%, latent HW defect ->
   owned drills incl $1.5B bridge -> FDE = same work, hands-on, in the field.

SCRIPT:
"I'm a technical program manager at Microsoft on the Azure reliability side — my
whole job is making sure the platform can actually recover when hardware fails. I
studied computer science at the University of Houston with a math minor, and I've
spent the last couple of years working right at the seam where software meets real
physical infrastructure: racks, nodes, networking, failure scenarios.

The thing I'm proudest of is that I led Azure's first proactive recovery drill —
took it from a concept to a live end-to-end execution in about four months. We hit
a ~94% autonomous recovery rate and actually surfaced a latent hardware defect that
wouldn't have shown up until a real outage. I've owned drills end-to-end since then,
including a network-isolation drill supporting a $1.5 billion contract where I ran
the live bridge under VP visibility.

What draws me to this role is that it's the same work I love but closer to the edge
— deploying and supporting real systems in the field, hands on the hardware, solving
problems where there's no one to escalate to. I'm a CS-trained generalist who's
comfortable in the messy space between software and hardware, and that's exactly
what Forward Deployed Engineering is."

(30-45 sec trim: para 1 + "first proactive drill / 94%" + last two sentences. Drop
 the $1.5B bridge to save time — save it for the behavioral round.)


================================================================================
Q2 — WHY ANDURIL / WHAT DO THEY DO  (keep SHORT)
================================================================================
BEATS WHAT: autonomous defense systems + Lattice (AI C2 OS fusing sensors -> one
   operator runs many unmanned systems). Mission Autonomy = teams collaborate across
   air/land/sea under one operator.
BEATS WHY: (1) mission matters at the sharp end (2) 2yrs at SW/HW seam -> FDE is that
   instinct in the field.

SCRIPT — WHAT ANDURIL DOES:
"Anduril builds autonomous defense systems — drones, sensors, counter-UAS — and ties
them together with Lattice, an AI-powered command-and-control OS that fuses sensor
data into a single real-time picture so one operator can direct many unmanned systems.
Mission Autonomy is the piece where teams of those systems collaborate across air,
land, and sea under one operator."

SCRIPT — WHY ANDURIL:
"Two reasons. First, the mission — I want the reliability work I do to matter at the
sharp end, and defending people is about as real as it gets. Second, the role itself:
I've spent two years at the software-hardware seam making systems recover under
pressure, and FDE is that same instinct taken to the field — deploy it, support it,
fix it where it actually runs. That's the work I want to be doing."


================================================================================
Q3 — WHY ARE YOU LEAVING MICROSOFT?
================================================================================
BEATS: grew a lot (guidance->owning drills) BUT work is remote from the hardware ->
   I light up for hands-on, catching the HW defect was my year's highlight -> FDE is
   that full-time + mission matters more. "Not running from MS, running toward
   hands-on + consequential."

SCRIPT:
"I've grown a lot at Microsoft — I went from needing close guidance on every drill
to independently owning them end-to-end, and I'm grateful for that. But the work is
fundamentally remote from the hardware. I plan drills against racks and nodes I never
physically touch, and I coordinate through bridges. What I keep gravitating toward is
the hands-on side — the one time we surfaced a real latent hardware defect was the
most satisfying moment of the year. FDE is that, full-time: in the field, on the
system, owning the outcome. And honestly the mission matters to me more here. I'm not
running from Microsoft; I'm running toward work that's more hands-on and more
consequential."

(If pushed "why not just go more technical inside Microsoft?": "I looked at that. The
 roles near me are still program-side and still remote from the hardware. This is a
 cleaner step to the work I actually want — field-deployed, hands-on, mission-driven.")


================================================================================
Q4 — QUESTIONS TO ASK THEM  (pick 3-4 — NOT a script; tailor to the room)
================================================================================
BEATS: field vs Costa Mesa split? | best FDE w/ no one to call — great vs good? |
   hardest problem now, HW/integration or Lattice/software? | ramp for program vs
   sysadmin background? | how do you capture field knowledge? (mention you built it)

FOR THE HIRING MANAGER / TEAM:
- "What does a deployment actually look like day to day for someone on Mission
  Autonomy — how much is in the field vs. at Costa Mesa?"
- "When a system fails in the field and there's no senior engineer on the line, what
  does your best FDE do in that moment? What separates great from good here?"
- "What's the hardest class of problem the team is hitting right now — is it more on
  the hardware/integration side or the Lattice/software side?"
- "How does the team capture and share field knowledge so the same problem doesn't
  get re-solved on every deployment?" (mention you built exactly this — the Copilot
  Studio drill agent — if it fits)

FOR THE RECRUITER / PROCESS:
- "What does the ramp look like for someone coming from a program/reliability
  background rather than a pure sysadmin one? How do you get them field-ready?"
- "What's the travel rhythm realistically — long deployments or shorter, frequent trips?"

ON GROWTH / MISSION:
- "Where do people on this team tend to go next — deeper technical, or leading deployments?"
- "What's a recent deployment the team is proud of?"

(Avoid: comp/benefits in early rounds; anything Google-able from the JD.)


================================================================================
Q5 — WHY FDE AND NOT PM / TPM?
================================================================================
BEATS: I love the technical hands-on part, not coordination -> as TPM I'm one step
   removed -> FDE puts me ON the system -> have program instincts but want to BE the
   one doing the technical work, not managing from a bridge.

SCRIPT:
"Because the part of my job I light up for is the technical, hands-on part — not the
coordination. My favorite moments aren't the status reviews; they're when I'm deep in
a failure scenario figuring out why a node won't recover, or catching a hardware
defect nobody else saw. As a TPM I'm one step removed from that — I direct the work
but I don't have my hands on the system. FDE puts me directly on it: deploy it, debug
it, fix it in the field. I have the program instincts — ownership, working across
teams under pressure, structuring chaos — but I want to apply them as the person
actually doing the technical work, not managing it from a bridge. That's the move."


################################################################################
#  SECTION 2 — RECRUITER SCREEN (fit + logistics; say them clean + confident)
################################################################################

================================================================================
>> "Walk me through your background."   (same content as Q1)
================================================================================
BEATS: CS+math -> TPM Azure reliability -> first proactive drill 94% + HW defect ->
   owned drills incl $1.5B bridge -> want hands-on + field.

SCRIPT:
"Sure. I studied computer science with a math minor at the University of Houston,
and for the last couple of years I've been a technical program manager at Microsoft
on Azure's reliability side. My job is basically making sure the platform can recover
when hardware fails — I design and run failure drills against real racks and nodes.
The highlight was leading Azure's first proactive recovery drill, taking it from a
concept to a live execution in about four months. We hit around a 94% autonomous
recovery rate and actually caught a latent hardware defect that wouldn't have shown
up until a real outage. Since then I've owned drills end-to-end, including one
supporting a $1.5 billion contract where I ran the live bridge under VP visibility.
What's pulling me toward this role is that it's the same work I love — keeping real
systems running — but hands-on and in the field, which is where I want to be."

================================================================================
>> "Why Anduril, why this role?"
================================================================================
BEATS: mission first (matters at the sharp end) + 2yrs SW/HW seam -> FDE is that in
   the field. Clean fit.

SCRIPT:
"Two reasons. The mission first — I want the reliability work I do to actually matter
at the sharp end, and defending people is about as real as it gets. And then the role
itself: I've spent two years at the seam where software meets physical hardware,
making systems recover under pressure. Forward Deployed Engineering is that same
instinct taken to the field — deploy it, support it, fix it where it actually runs.
That's exactly the work I want to be doing, so this role is a really clean fit."

================================================================================
>> "Are you genuinely okay being on-site in Costa Mesa — no remote/hybrid?"
================================================================================
BEATS: Yes, happy to relocate, the on-site/hands-on IS the appeal. No hesitation.

SCRIPT:
"Yes, completely. I'm happy to relocate to Costa Mesa, and honestly the on-site,
hands-on nature is part of the appeal — I want to be physically with the systems, not
remote from them. No hesitation there."

================================================================================
>> "Up to 75% travel, deployments up to 2 months in remote regions — good with that?"
================================================================================
BEATS: Yes, I'm in — actively want it, nothing ties me down.

SCRIPT:
"Yes, I'm in. I know what I'm signing up for and that kind of travel and field time
is something I actively want, not something I'm tolerating. I don't have anything
that ties me down, so the deployment rhythm works for me."

================================================================================
>> "Are you eligible to obtain/maintain a US Secret or Top Secret clearance?"
================================================================================
BEATS: Yes — US citizen, eligible. Don't hold an active one currently. (TRUTHFUL)

SCRIPT:
"Yes. I'm a US citizen and I'm eligible to obtain one. To be clear, I don't currently
hold an active clearance — but there's nothing in my background that would prevent me
from getting one, and I'm fully willing to go through the process."

================================================================================
>> "Can you meet the medical/deployment health requirements?"
================================================================================
BEATS: Yes, good health, ready for the standard process.

SCRIPT:
"Yes. I'm in good health and I don't have any conditions that would limit me from
deploying or meeting the physical requirements of the role. Whatever the standard
process is, I'm ready to go through it."

================================================================================
>> "What are your salary expectations?"
================================================================================
BEATS: DEFER + bounce back — "What range did you have in mind?" Don't undersell
   (clearance + travel + on-site premiums).

SCRIPT:
"I'd rather understand the full picture of the role and where it sits in your band
before anchoring on a number — I'm confident we can land somewhere that works for
both of us. If it's helpful for me to give a range, I'm happy to once I know a bit
more about the level and total comp structure. What range did you have in mind for
this position?"


################################################################################
#  SECTION 3 — TECHNICAL / TROUBLESHOOTING (narrate the tree, honest on depth)
################################################################################

================================================================================
>> "Troubleshoot a system that won't boot / lost network in the field, alone."
================================================================================
BEATS: stay methodical + document as I go. No-boot: power/connections -> POST/firmware
   -> boot media/OS -> logs -> isolate HW vs SW (minimal config, swap part). Network:
   link up -> ping -> IP/subnet/gateway -> DNS -> firewall. "Same muscle as drills."

SCRIPT:
"First thing — I stay methodical and I document as I go, because in the field there's
no one to escalate to and I don't want to lose track of what I've already ruled out.
I work from the physical layer up. For a no-boot: I'd check power and connections
first — lights, cabling, anything obviously loose or dead. Then POST and firmware —
is it getting through hardware init, am I getting beeps or error codes? Then boot
media and OS — is it finding the disk, is the bootloader intact? If I can get to
logs, I read them. The whole time I'm trying to isolate hardware versus software by
simplifying — strip it to a minimal config, swap a suspect component if I have a
spare. For lost network it's the same discipline: is the physical link up — cable,
interface lights — then can I reach anything at all with a ping, is my IP, subnet,
and gateway right, can I resolve DNS, is a firewall or ACL in the way. I narrow it
one layer at a time. Honestly, this is the same muscle I use running recovery drills
at Azure — calm, structured, document-as-you-go — just with my hands on the box
instead of over a bridge."

================================================================================
>> "A service is down on a Linux box — how do you diagnose it?"
================================================================================
BEATS: systemctl status -> journalctl -u -> process running (ps/top) -> resources
   (df -h/free/CPU) -> recent change/deploy -> dependency down. (status/logs/process/
   resources/deps/changes, in order.)

SCRIPT:
"I'd start with systemctl status on the service to see if it's running, failed, or
stuck, and what it says. Then journalctl -u for that service to read the actual logs
and find the error. If the logs point somewhere, I follow it. If not, I check the
basics: is the process actually running with ps or top, is the box out of resources —
disk full with df -h, memory with free, CPU pegged. I'd check whether a recent config
change or deploy broke it, and whether a dependency it relies on — a database, a
network mount — is itself down. Basically: status, logs, process, resources,
dependencies, recent changes. I work it in that order until something doesn't line up."

================================================================================
>> "Two devices can't talk on a network — how do you debug it?"
================================================================================
BEATS: link up (NIC/cable) -> ping device + gateway -> IP/subnet/mask (mismatch common)
   -> traceroute -> DNS (if name fails) -> firewall/ACL -> service listening (ss/netstat).

SCRIPT:
"I work up the stack. First, is the physical link even up — interface lights, cable,
is the NIC showing the interface as up. Then layer three — can I ping the other
device, can I ping the gateway. If ping fails, I check IP, subnet mask, and gateway
on both ends — a subnet mismatch is a really common culprit. Then traceroute to see
how far the traffic actually gets and where it dies. If it's reachable by IP but not
by name, it's DNS, so I check resolution. And if everything looks right but traffic
still won't pass, I look at firewalls or ACLs blocking the port. I also confirm the
service is actually listening on the port I expect with ss or netstat. Reachability,
addressing, routing, DNS, firewall, listening service — that's the order."

================================================================================
>> "What happens when you run a Docker container? / Why is a K8s pod failing?"
================================================================================
BEATS: container = isolated process from image (own fs/namespaces, shares kernel).
   Pod fail: kubectl describe (events) -> logs -> image pull / OOM / probes / crashloop.
   HONESTY: "adjacent via Azure infra, not prod K8s daily, but reason through it + ramp fast."

SCRIPT:
"A container is basically an isolated process — it runs from an image and gets its own
filesystem and namespaces, so it's separated from the host and other containers but
shares the host kernel. When you run one, Docker pulls the image if it's not local,
sets up that isolation, and starts the process defined in the image. For a failing
Kubernetes pod, I'd start with kubectl describe pod to read the events — that usually
tells you a lot — then kubectl logs for the container's actual output. Common causes
I'd check: the image failed to pull, it's hitting resource limits and getting
OOM-killed, a readiness or liveness probe is failing, or it's in a crash loop because
the process keeps exiting. I'll be straight with you — I've worked adjacent to this
through Azure infrastructure rather than running production Kubernetes myself day to
day, but I'm comfortable reasoning through it and I ramp fast on the hands-on side."

================================================================================
>> "Describe a system end-to-end that you set up or maintained — hardware to software."
================================================================================
BEATS: proactive drilling, built from nothing. HW: real racks/nodes + rack->node->
   service mapping (Altus). Middle: execution model + runbooks. Top: Copilot agent +
   docs. 94% + HW defect. "Exactly the HW/SW seam I want to work at."

SCRIPT:
"The closest end-to-end ownership I have is Azure's proactive drilling capability,
which I built from nothing. On the hardware side it operates against real racks and
nodes — and a big blocker early on was that we didn't have clean observability from
rack to node to service, so I partnered with the Altus engineers to deliver that
mapping in production. That gave us targeting: we could point a drill at a specific
rack, take down nodes, and validate that the platform recovered. On the software and
process side I defined the execution model, built the runbooks, and even built a
Copilot Studio AI agent off the playbook so the team could self-serve the steps. So
it spans the stack — physical rack and node behavior at the bottom, observability and
recovery logic in the middle, and tooling and documentation on top. The first full
execution recovered about 94% of nodes autonomously and surfaced a latent hardware
defect, which is exactly the kind of hardware-software seam I want to keep working at."

================================================================================
>> "Comfort assembling/repairing, low/high-voltage components?"
================================================================================
BEATS: comfortable w/ assembly/swap/cabling + 2yrs real rack/node exposure. High-
   voltage = want proper training first. DON'T overclaim (safety). Lead w/ real HW exposure.

SCRIPT:
"I'll be honest and calibrated here. I'm comfortable with hands-on hardware work —
assembling, swapping components, cabling, working through a system physically — and
I've spent two years working against real rack and node hardware, so I'm not coming
in cold to the physical side. On high-voltage specifically, I'd want proper training
and to respect the safety procedures before I'm working on it unsupervised — I'm not
going to overstate that. What I can promise is that I learn hands-on systems fast and
I'm meticulous about safety and documentation. I'd rather tell you exactly where I am
than oversell it and create a safety problem in the field."

================================================================================
>> "Customer's system is failing mid-operation, they're frustrated — what do you do?"
================================================================================
BEATS: stay calm + own it out loud -> stabilize before diagnose -> communicate
   constantly -> methodical. Anchor: led the $1.5B Sovereign BLEU live bridge.

SCRIPT:
"First, I stay calm and I take ownership out loud — the customer needs to know
someone has it. I acknowledge the impact directly: 'I understand this is down and
it's affecting your operation, I'm on it.' Then I separate stabilizing from
diagnosing — my first priority is getting them to a working state, even a degraded
one, before I chase root cause. I communicate as I go so they're never wondering
what's happening — short, clear updates. And I work the problem methodically instead
of flailing, the same diagnostic discipline I'd use on any failure. I've actually
done a version of this under real pressure — during the Sovereign BLEU drill, which
supported a $1.5 billion contract, I stepped in and led the live bridge mid-execution,
coordinating multiple teams and making real-time calls with VP-level visibility. So
the part where things are going sideways and people are stressed and you have to stay
calm and drive it — that's a situation I've been in and delivered in."

HONESTY LINE TO KEEP IN POCKET (use if they probe technical depth):
"My hands-on depth on some of this is still growing — my background is reliability
program work at the infra seam. But I learn systems fast and make them teachable;
that's documented in how I ramped on Azure's recovery stack and built tooling so
others could too. Give me the system and I'll own it."


################################################################################
#  SECTION 4 — BEHAVIORAL (STAR — Anduril weights ownership + ambiguity + learn-fast)
################################################################################
(Two stories — "frustrated stakeholder" and "disagreement" — aren't spelled out
 verbatim in your review; they're built from real events in it [DCOPS scoping; the
 Avail-Platform/DMS FcShell pushback], NOT invented. Flagged inline. Deliver confidently.)

================================================================================
>> "Tell me about a time you owned a problem end-to-end with no clear playbook."
================================================================================
BEATS: proactive drilling blank-page -> repeatable program. Defined exec model,
   partnered Avail/DMS, built rack->node->service mapping (Altus), drove first exec.
   4mo, 94%, latent HW defect. Now scaling to weekly cadence.

SCRIPT:
"The best example is building Azure's first proactive recovery drill. The situation
was that we had unused drill slots and no way to turn them into actual recovery
signal — there was no proactive-drill capability, no template, nothing to copy. I was
asked to figure out if we could make it real. So I owned the whole thing: I defined
the execution model from scratch, partnered with the Availability Platform and DMS
teams to pin down the requirements, and I unblocked a critical gap — we didn't have
clean observability from rack to node to service, so I worked with the Altus engineers
to ship that mapping in production, which gave us the targeting we needed. Then I drove
the first end-to-end execution: scenario design, partner alignment, execution planning,
recovery validation. We landed it in about four months, hit roughly a 94% autonomous
recovery rate, and surfaced a latent hardware defect that wouldn't have shown up until
a real outage. The thing I'm proudest of is that it didn't stay a one-off — it became a
repeatable program, and the team's now scaling it toward a weekly cadence. That whole
arc, from blank page to repeatable capability, is the kind of ownership I want to bring
to the field."

================================================================================
>> "Learn a complex system fast and then teach it to someone else."  [PREP HARD]
================================================================================
BEATS: drill knowledge stuck in experts' heads -> made it self-serve: reorganized hub,
   playbook->operating guide, built Copilot drill agent, newsletters ~10k. Cut inbound
   dep. "Learn deeply then make it teachable = the FDE loop." (maps to "teacher and student")

SCRIPT:
"At Azure, drill knowledge lived in the heads of a few experts — including me, once I'd
ramped — and the whole team kept getting pinged for the steps, which was a bottleneck.
I'd had to learn the recovery stack and the drill procedures pretty fast myself, and
once I had, I didn't want that knowledge stuck in a few people's heads. So I made it
teachable. I reorganized our engineering hub, took the scoped-drill playbook and turned
it into an actual operating guide that service teams could follow on their own, and then
I went a step further and built a Copilot Studio AI agent off that playbook — so anyone
could just ask it for drill steps, timelines, and procedures without needing an expert
on the line. I also shipped newsletters to around ten thousand readers to keep everyone
current on outcomes. The result was that inbound dependency on our team dropped and we
got our capacity back for higher-impact work. That loop — learn a system deeply, then
make it so others don't have to learn it the hard way — is exactly what a forward
deployed engineer does when they're documenting field fixes so the next deployment
goes smoother. It's the part of the work I genuinely enjoy."

================================================================================
>> "Worked under high pressure / a system down / high-stakes execution."
================================================================================
BEATS: Sovereign BLEU, $1.5B contract, VP visibility. Stepped in, led the main bridge —
   coordinated teams, real-time calls, held continuity. "I get calmer + more structured
   under pressure, not more scattered." = field-ops temperament.

SCRIPT:
"The Sovereign BLEU network-isolation drill is the one that comes to mind. It supported
a $1.5 billion contract and it had VP-level visibility, so there was real pressure and
no room to fumble it. Partway through execution, I stepped in and led the main bridge —
which meant coordinating multiple teams in real time, making decisions on the fly as
things developed, and keeping everyone aligned so we didn't lose execution continuity.
The drill completed successfully and we held continuity the whole way through. What I
took from it is that I'm at my best when the stakes are high and things are moving fast —
I get calmer and more structured, not more scattered. That's a big part of why field
work appeals to me: when a system's down in the field and there's pressure and no one to
escalate to, that's the situation I want to be the steady hand in."

================================================================================
>> "Dealt with a frustrated customer or stakeholder."
================================================================================
BEATS: DCOPS — came in w/ over-ambitious full-automation plan, they were skeptical.
   Listened, walked their workflow, agreed full automation not near-term, authored a
   real spec for next Drills Platform. Turned frustrated -> bought-in. "A frustrated
   stakeholder is usually telling you something true."
   [GROUNDING: real DCOPS scoping story. Truthful.]

SCRIPT:
"When I started working on automating the DCOPS maintenance-conflict checks, I came in
with an ambitious plan to fully automate it. The DCOPS stakeholders were — fairly —
skeptical and a bit frustrated, because I was underestimating how complex their
evaluation workflow actually was, and they'd seen people breeze in with
oversimplified solutions before. Instead of pushing my plan, I slowed down and really
listened to walk through their process with them. Once I understood it, I agreed full
automation wasn't realistic in the near term — but rather than just drop it, I authored
a detailed spec that captured their real constraints and positioned it to get built into
the next iteration of the Drills Platform. That turned the relationship around: they went
from frustrated to bought-in, because they could see I'd actually heard them and was
delivering something real instead of something convenient for me. The lesson I carry is
that a frustrated stakeholder is usually telling you something true — the move is to
listen first, then deliver incremental value you can both stand behind."

================================================================================
>> "Disagreed with a teammate or a decision — how'd you handle it?"
================================================================================
BEATS: my own FcShell plan; Avail/DMS pushed back as risky; I validated -> they were
   right (Service Healing -> data loss); pivoted mid-flight, disabled Anvil Recovery.
   "Separate ego from the plan, validate the claim, change course fast. Being right >
   being the one who was right."
   [GROUNDING: IS in your review. Honest.]

SCRIPT:
"During the proactive-drilling launch, my own initial plan used an FcShell script
workaround to manage node HI-state during the rack-level drill. I was confident in it
and ready to move fast. But when I dug in with the Availability Platform and DMS teams,
their read was that my approach was risky — and as I investigated, they were right:
nodes entering HI state would trigger Service Healing, which would migrate VMs and risk
data loss. That's an unacceptable outcome. So this was a case where the disagreement was
with my own approach, and the partner teams were pushing back. I didn't dig in to defend
my plan — I treated their pushback as signal, validated it myself, and then pivoted the
entire execution strategy mid-flight, ultimately disabling Anvil Recovery so we could run
the drill safely. The drill went off cleanly. How I handle disagreement is: I separate my
ego from the plan, I go validate the technical claim rather than argue it, and if they're
right, I change course fast. Being right matters more to me than being the one who was
right."

================================================================================
>> "Tell me about a failure and what you learned."
================================================================================
BEATS: same FcShell — moved before stress-testing assumptions; would've caused data
   loss; pivoted mid-flight. LESSON: validate assumptions early w/ partner teams, test
   against real platform behavior before committing. "In the field a bad assumption
   costs a deployment."

SCRIPT:
"My clearest one is that same FcShell approach during proactive drilling. My instinct
was to move fast, and I'd committed to a workaround before fully validating how it would
behave against the live platform. It was only after deeper investigation with the
Availability Platform and DMS teams that I realized it would trigger Service Healing and
risk data loss — a serious problem I hadn't caught up front. I had to pivot the whole
execution strategy mid-flight to do it safely. The failure was real: I'd moved before I'd
stress-tested my assumptions. What I learned, and genuinely changed, is to validate
assumptions early with partner teams and to test the plan against real platform behavior
before committing — especially in high-risk scenarios. I still value speed, but I balance
it with cross-team technical validation now. For field work, that lesson feels especially
important: in the field a bad assumption can cost you a deployment, so catching it early
is everything."

(Why leave Microsoft + Why FDE not PM/TPM = see Q3 and Q5 above. Same scripts apply.)


################################################################################
#  SECTION 5 — MISSION-FIT (CONVICTION — they screen out the ambivalent)
################################################################################

================================================================================
>> "How do you feel about working in defense / building weapons systems?"
================================================================================
BEATS: genuinely bought in, NOT neutral. Credible deterrence keeps people safe; want
   serious people building it. 2yrs making infra reliable -> same rigor where it protects
   lives. "I want to be in the room." (DELIVERY: conviction + eye contact, no hedging.)

SCRIPT:
"I'm genuinely bought in — this isn't a neutral 'I can live with it' for me. I believe
credible deterrence is what actually keeps people safe, and I'd much rather the people
building these systems be serious, thoughtful, and careful about it. I've spent two
years making critical infrastructure reliable because reliability protects people, and
I want to apply that same rigor where it protects lives directly. The mission is a big
part of why I'm here, not something I'm setting aside to get the job. I want to be in
the room building this."

================================================================================
>> "What do you know about Lattice and our products?"
================================================================================
BEATS: Lattice = AI C2 OS, fuses sensors -> real-time picture, act fast. Mission
   Autonomy = teams of unmanned systems under one operator across air/land/sea. HW
   (Ghost/counter-UAS) + Lattice as the software brain. FDE = deploy/support the whole
   stack in the field. [VERIFY product names morning-of at anduril.com/lattice.]

SCRIPT:
"Lattice is your AI-powered command-and-control operating system — it takes in data
from a whole range of sensors and sources and fuses it into a single real-time picture
of what's happening, so an operator can understand the battlespace and act on it fast.
The piece that maps to this role is Mission Autonomy: instead of one operator running
one system, Lattice lets teams of unmanned systems — across air, land, and sea —
collaborate and operate together under a single operator's direction. On the hardware
side you've got the autonomous systems themselves — things like Ghost and the broader
counter-UAS and surveillance line — and Lattice is the software brain that ties them
together. As a forward deployed engineer on Mission Autonomy, I'd be the person
actually deploying and supporting that whole stack in the field — the hardware and the
software working as one system — which is exactly the seam I want to work at."


################################################################################
#  DELIVERY REMINDERS
################################################################################
- Learn the BEATS, not the words. Reciting = obvious. Let it sound like you.
- Calibrated honesty is a STRENGTH — don't overclaim K8s / high-voltage.
- When they question "program guy, can he do hands-on?" -> lead with the hardware-defect
  discovery + the fact you BUILD tooling, not just coordinate.
- Conviction on the mission. Ambivalence gets screened out.
- Verify Lattice/product names the morning of at anduril.com/lattice.
================================================================================
END
================================================================================
