import re

dead_slugs = {
    "datacurve", "materialize", "handoff", "abundant", "harper",
    "interfaceai", "vitablehealth", "latentai", "snackpass", "credera",
    "cascade", "luma", "forge", "doe"
}

with open("companies.yaml") as f:
    lines = f.readlines()

result = []
i = 0
removed = []
while i < len(lines):
    line = lines[i]
    if line.strip().startswith("- name:"):
        block = [line]
        j = i + 1
        slug = None
        while j < len(lines) and not lines[j].strip().startswith("- name:"):
            block.append(lines[j])
            m = re.match(r"  slug: (\S+)", lines[j])
            if m:
                slug = m.group(1).strip()
            j += 1
        if slug in dead_slugs:
            removed.append(slug)
            i = j
        else:
            result.extend(block)
            i = j
    else:
        result.append(line)
        i += 1

with open("companies.yaml", "w") as f:
    f.writelines(result)

print(f"Removed {len(removed)} dead boards: {sorted(removed)}")
print(f"Lines after: {len(result)}")
print(f"Companies after: {sum(1 for l in result if l.strip().startswith(chr(45) + chr(32) + chr(110) + chr(97) + chr(109) + chr(101) + chr(58))}" )
