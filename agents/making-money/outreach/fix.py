path = "/home/azureuser/.openclaw/agents/making-money/workspace/outreach/find-and-send.py"
with open(path, "rb") as f:\n    data = f.read()\ndata = data.replace(b"except Exception as e:\\n            print", b"except Exception as e:\n            print")
with open(path, "wb") as f:\n    f.write(data)\nprint("Fixed")
