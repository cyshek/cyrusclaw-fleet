# Cover answers — Tenexlabs, Forward Deployed Engineer (tenex-2a359a2a-d5ed-48e8-96b8-b93826110ee9)

## Full Name

Cyrus Shekari

## What did you study in college?

Bachelor of Science in Computer Science with a minor in Mathematics at the University of Houston. Graduated December 2024 with a 3.8 GPA. Coursework included Data Structures, Algorithms, Databases, Artificial Intelligence, and Machine Learning.

## What specifically interests you about joining Tenex at this stage? What's driving your interest in making a move right now?*

At Microsoft I've shipped production AI systems - an agent that reduced resilience drill planning cycle time by 39%, a RAG-backed semantic search system that cut lookup time by 83%, a platform now serving Databricks, Walmart, SAP, and NetApp. The work I find most energizing is the part where you walk into an unfamiliar stack, figure out the right architecture, and ship something that keeps running after you leave. That's the whole job description at Tenex, not just a slice of it. Right now my role blends program management, stakeholder coordination, and engineering. I want to go deeper on the engineering side, own the code end-to-end, and work on a tighter loop between what I build and what it actually changes for the client.

Tenex specifically appeals to me because of where it sits in the stack - embedded inside Fortune 500 operations, partnered directly with Anthropic and OpenAI's Applied AI teams, shipping the kind of production agentic systems that most companies are still treating as prototypes. The problems are real, the clients are serious, and the bar is that it runs on Monday morning without anyone from Tenex in the room. That framing matches exactly how I think about what makes engineering work worth doing. The uncapped variable tied to throughput is also an honest signal - it means the firm actually measures output, not activity, and rewards people who ship.

## Tell us about a technical decision you got meaningfully wrong. What did it cost (time, money, downtime) and what do you do differently now? Give us a number if you can.

Early in building Azure's Resilience Automation Platform, I made a decision to keep drill scheduling logic tightly coupled to a single internal tooling layer that the core Azure platform team owned. My reasoning was straightforward - it was already there, it worked for the initial scope, and building around it felt faster than abstracting it. That was wrong. When we scaled from a two-person operation to serving Databricks, Walmart, SAP, and NetApp across 45+ annual drills, that dependency became a bottleneck every time the platform team had competing priorities. Coordination overhead alone cost me an estimated 3-4 weeks of avoidable delay over roughly two quarters, and there were stretches where I couldn't unblock client-facing work without waiting on a team that had no stake in my timeline.

What I do differently now is treat external dependencies as a risk surface from the start, not something to revisit when they cause pain. Before I commit to building on top of something I don't control, I ask what happens to my delivery if that team deprioritizes me for two weeks. If the answer is bad, I scope the abstraction layer early, even if it costs time upfront. The 3-4 weeks I lost to that coupling would have more than covered the work to isolate it properly.

## What's a widely accepted engineering practice, tool, or trend you think is overrated? What do you do instead?

Comprehensive upfront documentation for internal tooling. The instinct is understandable - write the spec, get sign-off, then build. In practice, especially on AI workflow systems where the behavior of the model shapes what's even possible, the spec is frequently wrong by the time the code exists. I've watched teams spend two weeks writing requirements documents for agentic systems where the first prototype surfaced constraints nobody anticipated, and the document became a liability because stakeholders anchored to it.

What I do instead is ship a tight, opinionated prototype as fast as possible and treat that as the spec. Real behavior in front of real users surfaces the actual requirements faster than any document. I still write things down - architecture decisions, edge case handling, audit trail logic, anything that needs to survive past me - but I write it after I understand the problem, not before. For the AI systems I've built at Microsoft, that approach consistently tightened the feedback loop and produced cleaner final systems than the upfront-spec path would have. The discipline is in knowing which decisions need to be locked early versus which ones you're better off learning from the prototype.

## What's something you understand unreasonably well  (Postgres internals, a niche protocol, vim, anything) and what's one non-obvious thing about it that most engineers get wrong?

Retrieval-augmented generation pipelines, specifically the retrieval half. I built a production RAG-backed semantic search system for Azure documentation that cut lookup time by 83%, and I spent a disproportionate amount of time understanding why retrieval fails before I understood how to make it work reliably.

The non-obvious thing most engineers get wrong is treating chunk size as a tuning knob they'll optimize later, when it's actually one of the most load-bearing architectural decisions in the whole pipeline. The intuition is usually to chunk aggressively - smaller chunks, more granular retrieval, better precision. In practice, too-small chunks strip the surrounding context that makes a passage meaningful to the model, so you retrieve the right sentence and the model still generates a bad answer because it's missing the three sentences that gave that sentence its meaning. The failure mode is subtle because your retrieval metrics can look fine while your generation quality is quietly degraded. What I do is design chunks around semantic units - a complete argument, a full procedure, a self-contained explanation - and then test generation quality directly, not just retrieval recall. Most teams don't instrument that gap until they're already debugging production complaints.

## Link something you've built that you're proud of (repo, PR, demo, launch, blog post). In 3–4 sentences, what would you change about it today?

The most concrete public artifact I can point to is my GitHub at github.com/cyshek - the work I'm proudest of sits inside Microsoft's internal systems and isn't publicly linkable, specifically the production AI agent for resilience drill planning and the RAG-backed semantic search system for Azure documentation. If I could rebuild the semantic search system today, I would instrument the gap between retrieval quality and generation quality from day one rather than treating them as separate concerns measured separately. I would also build the chunking strategy around explicit semantic unit tests rather than tuning chunk size empirically after the fact, which is where I lost the most time during iteration. And I would design the metadata schema with downstream filtering in mind from the start - the schema I shipped worked, but it required a cleanup pass when retrieval requirements evolved, which was avoidable.
