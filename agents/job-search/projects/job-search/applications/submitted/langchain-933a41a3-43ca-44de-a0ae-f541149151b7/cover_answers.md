# Cover answers — Langchain, Solutions Architect (Dallas) (langchain-933a41a3-43ca-44de-a0ae-f541149151b7)

## Full Name

Cyrus Shekari

## What is the best agent use case you're proud of building?

The one I'm most proud of is an internal AI agent I built at Microsoft for resilience drill planning on Azure. The core problem was that planning a single drill involved a lot of manual coordination across teams, pulling context from multiple sources, and producing structured outputs that had to meet strict operational requirements. I integrated LLM-powered automation into that workflow, turning what had been a slow, high-touch process into something the agent could drive with minimal human intervention. The results were concrete: 39% reduction in planning cycle time and a 21% expansion in overall drill capacity.

What made it genuinely interesting from an agent engineering perspective was that it wasn't just a chatbot or a one-shot prompt. It had to handle structured planning workflows, interact with real scheduling and infrastructure data, and produce outputs that production teams would trust and act on. I had to think carefully about how the agent managed state across the planning lifecycle, how it handled edge cases and incomplete inputs, and how to evaluate whether its outputs were actually good before anyone relied on them in an operational context. That experience of taking an agent from concept to something running at cloud infrastructure scale, with real business impact, is what I'd point to as my clearest example of production-grade agent engineering.
