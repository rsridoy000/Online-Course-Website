import os

views_path = r'g:\files\quiz_app\quiz_app\views.py'
out_path = r'g:\files\quiz_app\scratch\func_lines.txt'

with open(views_path, encoding='utf-8') as f:
    lines = f.readlines()

defs = []
for idx, line in enumerate(lines):
    if 'def ' in line:
        defs.append(f"{idx+1}: {line.strip()}")

with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(defs))
