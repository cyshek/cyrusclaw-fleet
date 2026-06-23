# Cover answers — Elevenlabs, Forward Deployed Engineer - Software Engineer (elevenlabs-6c4c57c1-ec72-42ba-af3a-eb7aebbde2e6)

## Full Name

Cyrus Shekari

## Why ElevenLabs, and why now?

My work at Microsoft has been fundamentally about sitting at the intersection of complex technical systems and the customers who depend on them. I've spent the last two years owning end-to-end execution for Azure's most strategic partners, translating technical constraints into clear architectures, and building AI-powered tooling to accelerate high-stakes operations. That's exactly the forward-deployed model: embedded with customers, hands-on with the code, accountable for outcomes. The FDE role at ElevenLabs maps directly onto how I already work, just in a context where the product itself is the thing I find most technically exciting right now.

ElevenLabs is making a specific and compelling bet - that AI voice and audio are foundational infrastructure, not a feature. The scale of that conviction is visible in how the product has expanded from a single voice model to three distinct platforms serving enterprises like Deutsche Telekom and Meta. I want to be building at that layer of the stack, with customers who are deploying real agents at scale. The combination of a genuinely differentiated technical product, a high-velocity team culture, and the moment the industry is at makes this the most interesting place I could be doing this kind of work right now.

## What's the most impactful thing you've built? What was your specific contribution?

The most impactful thing I've built is Azure's Resilience Automation Platform - a 0-to-1 internal system that took what was a manually coordinated, 2-person resilience drill operation and turned it into a platformized, self-service capability sustaining 45+ annual drills across strategic enterprise partners including Databricks, Walmart, SAP, and NetApp. I owned the full execution: defining the self-service scheduling requirements, working directly with engineering to translate those requirements into the product, and driving the operational transition away from manual coordination overhead. I also pioneered Azure's first proactive resilience testing capability within that program, delivering a rack-level drill program in 4 months with a 94% recovery rate.

Beyond the platform itself, I layered in an internal AI agent for drill planning and restructured automation workflows, which cut planning cycle time by 39% and expanded drill capacity by 21%. My specific contribution was the full ownership model - I wasn't advising, I was the person making the architecture decisions, writing the requirements, coordinating across 14+ cross-org teams, and delivering results under executive visibility. The $14M+ impact figure reflects the downstream value to partners, and it came from treating this less like a program management job and more like building a product from scratch.

## How did you know it worked? What did success actually look like?

Success had a few distinct signals. The clearest one was operational: before the platform, running a drill required constant manual coordination between teams. After, engineering teams could deploy and run drills without that overhead - the 30% reduction in operational toil was measurable and visible in how the team's time was actually spent. The 45+ drills sustained annually was a direct output of that capacity unlock.

The harder validation came from the rack-level proactive resilience program. A 94% recovery rate sounds like a success metric, but what actually confirmed it was working was that the remaining 6% surfaced real, previously undetected hardware defects. That was the point - not to run drills that pass, but to find the failures before customers do. When the program started catching critical defects that hadn't been visible before, that was proof the model was working. The $14M+ impact came from that early detection and the downstream cost avoidance it created for strategic partners.

For the AI agent piece, the 39% reduction in planning cycle time was quantified, but the qualitative signal was simpler: the team stopped asking me to manually pull context and generate plans. The tooling absorbed that work. That's the clearest sign automation has landed - when people stop doing the thing it replaced.

## Have you used ElevenLabs - even in a personal or side project? What did you build or explore?

Yes. I used ElevenLabs to build a voice layer on top of a personal productivity tool I was experimenting with - essentially a spoken daily briefing that pulled together calendar context, task priorities, and a few news sources, then read them back in a natural voice on a morning trigger. The core appeal was how quickly I could go from API key to a result that actually sounded like something worth listening to. Most TTS I'd worked with before had an obvious synthetic quality that made me tune it out after a few seconds. ElevenLabs didn't have that problem.

I also spent time exploring the multilingual capabilities after seeing the 70+ language support called out. I tested a few edge cases in Farsi, given my background, and was curious how the model handled phonemes that don't translate cleanly from English-trained systems. The results were notably better than I expected. That exploration informed a lot of my interest in the API platform specifically - the underlying model quality is what makes the enterprise use cases real, and I wanted to understand where the boundaries were before thinking about how customers would integrate against it at scale.
