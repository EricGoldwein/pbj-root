import re
from pathlib import Path

lines = Path("insights.html").read_text(encoding="utf-8").splitlines()
depth = 0
container_open = None
container_depth = None
for i, line in enumerate(lines, 1):
    opens = len(re.findall(r"<motion\b", line, re.I)) + len(re.findall(r"<div\b", line, re.I))
    closes = len(re.findall(r"</motion>\s*", line, re.I)) + len(re.findall(r"</motion>\s*", line, re.I))
    if 'class="container"' in line:
        container_open = i
        container_depth = depth + 1
    if re.search(r"<h2>\s*[56]\.", line):
        inside = container_depth is not None and depth >= container_depth
        print(f"h2 line {i}: depth={depth} inside_container={inside}")
    depth += opens - closes
print(f"container opens line {container_open}, depth={container_depth}, final depth={depth}")
