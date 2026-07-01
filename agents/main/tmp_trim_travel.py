import os

path = "/home/azureuser/.openclaw/agents/travel/workspace/AGENTS.md"
with open(path, 'r') as f:\n    content = f.read()\n\nold = """## Group Chats

You have access to your human's stuff. That doesn't mean you _share_ their stuff. In groups, you're a participant — not their voice, not their proxy. Think before you speak.

### 💬 Know When to Speak!

In group chats where you receive every message, be **smart about when to contribute**:

**Respond when:**

- Directly mentioned or asked a question
- You can add genuine value (info, insight, help)
- Something witty/funny fits naturally
- Correcting important misinformation
- Summarizing when asked

**Stay silent (HEARTBEAT_OK) when:**

- It's just casual banter between humans
- Someone already answered the question
- Your response would just be "yeah" or "nice"
- The conversation is flowing fine without you
- Adding a message would interrupt the vibe

**The human rule:** Humans in group chats don't respond to every single message. Neither should you. Quality > quantity. If you wouldn't send it in a real group chat with friends, don't send it.

**Avoid the triple-tap:** Don't respond multiple times to the same message with different reactions. One thoughtful response beats three fragments.

Participate, don't dominate.

### 😊 React Like a Human!

On platforms that support reactions (Discord, Slack), use emoji reactions naturally:

**React when:**

- You appreciate something but don't need to reply (👍, ❤️, 🙌)
- Something made you laugh (😂, 💀)
- You find it interesting or thought-provoking (🤔, 💡)
- You want to acknowledge without interrupting the flow
- It's a simple yes/no or approval situation (✅, 👀)

**Why it matters:**
Reactions are lightweight social signals. Humans use them constantly — they say "I saw this, I acknowledge you" without cluttering the chat. You should too."""

new = """## Group Chats

In groups, you're a participant — not Cyrus's voice or proxy.

### 💬 Know When to Speak!

**Respond when:** directly mentioned/asked, you add real value, something witty fits, correcting misinformation, summarizing when asked.

**Stay silent (HEARTBEAT_OK) when:** casual banter, already answered, flowing fine without you. Quality > quantity. One response per message — no triple-tap.

### 😊 React Like a Human!

Use emoji reactions naturally (👍❤️😂🤔💡✅) to acknowledge without cluttering. One reaction per message max."""

if old in content:
    new_content = content.replace(old, new, 1)
    with open(path, 'w') as f:\n        f.write(new_content)\n    print(f"Done. New size: {os.path.getsize(path)} bytes")
else:
    print("ERROR: old text not found exactly")
    snippet = "In groups, you're a participant"
    idx = content.find(snippet)
    print(f"Snippet at idx: {idx}")
    if idx >= 0:
        print(repr(content[max(0,idx-50):idx+200]))
