# Founding Product Manager

**Company:** Ekho
**Location:** New York City HQ
**Apply:** https://jobs.ashbyhq.com/ekho/4ce6d186-e9a0-4420-8af2-36112957de94
**Ashby Org:** ekho
**Ashby Job ID:** 4ce6d186-e9a0-4420-8af2-36112957de94

---

Prior to Ekho, one of the world's largest retail segments had no checkout button. If you wanted to buy a vehicle online, the best you could do was fill out an “I’m Interested” form and wait for someone to call you back. Found the bike of your dreams at a dealership two states away? You were mostly on your own. Tax requirements, titling workflows, and registration rules vary by state and county. Most dealers didn’t sell across state lines at all, because they had no reliable way to do it.

Now they can. A buyer finds a vehicle, clicks “Buy Now,” completes financing, titling, registration, and insurance verification online, and gets it delivered to their door in a few days. The whole thing takes as few as ten minutes. And the dealer doesn’t have to be at their desk (let alone awake) for any of it.

The first time one of our dealers woke up to a completed overnight sale, they messaged us: “Oh my God, this is crazy. We just fulfilled a transaction while the whole team was asleep.”

We get messages like this regularly now, and they’re no less exciting than the first one was. What made it possible was 18 months of untangling a combinatorics problem disguised as county-specific titling and registration, and integrating with 50 DMVs that still prefer faxes to APIs. That foundation is built. Now we’re putting AI on top of it, expanding into cars, and building the transaction layer that works both in-store and online.

One thing worth saying directly: Anthropic can’t ship something tomorrow that makes this company obsolete. The moat is the foundation beneath the code: the 50-state compliance framework, the DMV relationships, and the legal licenses we’ve secured. That’s not something you can prompt your way around. Unlike most startups right now, we’re not racing against the next model update.

### What you’ll own

Four user surfaces, all of which currently live between engineering, ops, and the founders. You’ll be working side-by-side with me and Chris across all of them.

**The buyer experience**. This includes the search results and vehicle detail pages on dealer websites, the “Buy Now” flow, and everything between a buyer landing on a page and completing a purchase. It's the part of the product that creates the ten-minute-checkout moment and the overnight-sale stories. *What’s open right now* are the decisions that would make the whole flow feel seamless to buyer and dealer alike. Some are about friction (where to introduce it, where to remove it). Others are about what a “magic moment” in a new dealer’s first week actually looks like.

**The dealer and OEM admin portals**. This is what a dealer sees when they log in to configure their store, manage inventory, track leads, and monitor transactions. Our customer range is large: a ten-car powersports shop and an 83-dealer OEM network share the same product surface. *What’s open right now*: the portal has been shaped reactively: dealers asked for things, and we built them. Nobody currently owns the question of how the admin experience scales across that range without cluttering it for small dealers or fragmenting the codebase.

**The AI Sales Agent and Transaction Engine**. The Sales Agent handles leads 24/7 across chat, SMS, and email; Victor shipped the whole thing to six paying clients in a single month. The Transaction Engine is the compliance and fulfillment backend underneath it that makes every sale legally operable. *What's open right now*: the Sales Agent’s next version needs deliberate prioritization instead of running on what-a-dealer-asked-for-last-week. Native calendar support, lead assignment routing, and richer tool support (trade-in estimations, service scheduling) are all things we would have shipped already with one more engineer and a PM.

**Internal operational tooling**. The systems our titling and customer support teams use to run hundreds of compliance-heavy workflows span all 50 states. Ali's team is ten people handling buyer calls, titling packets, tax compliance, and state-by-state processing. *What’s open right now*: Ali’s been leading a migration of the compliance infrastructure from the Notion-table architecture we built four years ago into 25+ interconnected systems. Ali holds the operational picture; Bongi holds the architectural one. The missing role will hold the product shape: how the migration sequences, what ships first, how the ops team’s workflow changes as each piece lands. (Ali will be relieved to hand this one off.)

This role isn’t just the first PM hire. We’re looking for someone around whom we can build the product organization. Your taste and judgment will shape not just what ships next, but how product gets made at Ekho going forward.

### Who you’ll work with

[Rowan](https://www.linkedin.com/in/rowan-mockler/) grew up in South Africa, where his dad owned a used car dealership. [Chris](https://www.linkedin.com/in/chris-g-howard/) grew up in Atlanta, and was close family friends with some of the largest dealer operators in the Southeast. They met at Stanford, went to see what good looked like at scale (Rowan at Duolingo, Chris at Meta), then went through YC determined to find the most overlooked problem in the largest industry they could. This one—a $2 trillion industry that couldn’t complete a sale online—was the one that stuck. 

[Bongi](https://www.linkedin.com/in/bongifleischer/), our VP of Eng, has known Rowan since high school. He turned down several of Rowan’s ideas before finally saying yes to this one. That kind of conviction from someone who knows the founder well enough to say “no” is its own kind of signal.

[Ali](https://www.linkedin.com/in/alifern/), our Head of Operations, leads the team that makes 50-state compliance actually work. Her grandpa and mom sold cars, her dad works at a dealer group, and her first internship was writing blogs about car models, so she came to Ekho the way some people come back to their hometown. She also runs marathons. She’ll be your most important day-to-day partner.

[Nisarg](https://www.linkedin.com/in/nisargshah155/) and [Charlie](https://www.linkedin.com/in/cdhirsch/) co-lead our Client & Product success team. They met at UNC and spend their non-work hours rooting for Carolina basketball. They hear every dealer complaint, every onboarding friction, every “when are we going to get X?” and they’ll bring those to you. You’ll decide which ones become the roadmap.

We’re 34 people, mostly in our mid-to-late twenties, with backgrounds across Stanford, YC, BCG, Goldman, and Meta. Nine of us are engineers. We spend four days a week together in our Flatiron office.

[Nadim](https://www.linkedin.com/in/nadim-el-jaroudi-53059090/) has kept every laptop from every job he’s ever had. They’re now racked in a server farm in his apartment running AI agents (before that it was crypto). [David](https://www.linkedin.com/in/davidreichek/) edits a sci-fi publication online and curates the strangest stories you’ve ever read. [Alexis](https://www.linkedin.com/in/alexisdrobles/) is working on becoming a DJ and producer (his genre is deep house). [Jon](https://www.linkedin.com/in/jwdallas/) studied film and posts photos to Slack that make everyone else’s iPhone photography look like a crime. [Rodrigo](https://www.linkedin.com/in/chousal/) can find the Spanish speakers in any room in New York, which is its own kind of superpower.

[Mike](https://www.linkedin.com/in/mike-cunningham-a28227a/) is our industry vet. He’s in sales, not engineering; but you'd never guess it from the Claude Code usage. He spent decades as an executive at Triumph, Piaggio, and Zero Motorcycles, and recently organized a motorcycle track day for the whole team because he found a free event and figured people would want to go. (They did.)

There’s a gong in the middle of the office that goes off without warning every time a sale closes. Engineering debates here are about architecture decisions, ownership boundaries, and what to name things. The naming convention debates alone have generated Slack polls with 15+ options, many of them so bad they’re good. The founders have never said “my way or the highway.” Engineers define *what* to build and *why*, not just *how*. The whole team has an unlimited Claude Code budget, and it’s not just an engineering thing. People across the company are shipping with AI.

### Who’ll thrive here

**You have a technical background (BS in CS or equivalent) and real instincts for architecture**. When we talk about a 50-state compliance migration or a multi-entity permissions model, you can hold the shape of the problem in your head without a translator. You’ll be in the codebase enough to understand what’s happening, but not coding all day. What we care about is whether you can make high-quality decisions about systems that are going to outlast you.

**You have design taste and can prototype**. You can take a problem, sketch five versions of what the solution could look like, and know which one to build first. Some of our strongest technical candidates have bounced off our prototype exercise because this instinct wasn’t there. We need it to be there.

**You work fluidly between 30,000 feet and 3 feet**. You can hold a strategy conversation with Rowan in the morning, write an API spec with Chris after lunch, and argue for a specific pixel on a checkout screen with Connie in the afternoon.

**You ship fast and get feedback faster**. You’d rather put a V1 in front of a dealer on Friday than spend another week refining it in isolation. You measure iteration in days, not sprints.

**You default to action**. When you see a problem nobody currently owns, your instinct is to pick it up rather than flag it.

**AI is already integrated into how you work**. You have Claude Code open and you’re prototyping with it. Everyone here (not just engineers) pushes code to our production codebase with it. You need to be comfortable doing the same when it speeds things up… and comfortable leaving it to the engineers when it doesn’t.

**You can say no**. Especially to dealers who are excited, and even when a founder is leaning toward yes, or when an engineer has already started building. Every current bottleneck at Ekho traces back to an unowned yes. If you struggle to say no, this job will make you miserable.

**You’d rather talk to a user than read a deck about them**. You don’t wait for research to be handed to you; you run it yourself, and the patterns you surface change what gets built.

**You’re low ego, coachable, and high-slope**. We’ve hit the limit on this one before. This is a team where a customer support teammate can push a PR, where naming-convention debates have 15 options, and where the best idea wins regardless of who’s in the room. We’d rather hire someone with raw skill who’s ready to learn than someone who walks in thinking they already know everything.

**You don’t mind long hours when the work is worth it**. The team is in at 8:30; dinner gets ordered at 7 for whoever’s still here… and most days, most people are.

### Comp & benefits

- $200-250k base

- Meaningful equity

- Annual bonus

- Health, dental, & vision

- 401(k)

- Free lunch and dinners

- $700/year work setup stipend

- Annual team offsite

## How we hire

After an initial screen with our recruiting team, you’ll have an intro call with Ali to get grounded in the role and the current product reality.

Then a conversation with Rowan about product vision and where we’d want to take Ekho together over the next two years.

Then a product walkthrough with Chris. You’ll bring something you’ve shipped, and we’ll dig into the decisions you made, the ones you didn’t, and what you'd do differently now.

The onsite is where it gets interesting. You’ll have a prototyping challenge—we’ll send a prompt in advance, and you’ll spend time building a working version of a product decision we’re actually weighing. We care as much about how you think about the problem as what you land on, which is why you’ll walk us through your reasoning with a group that includes at least one engineer.

After that, lunch with the team, and a conversation with Rowan or Chris to close the day.

We move fast when we find the right person. And we respect your time enough to be honest if it's not a fit.
