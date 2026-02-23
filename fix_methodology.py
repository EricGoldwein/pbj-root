# One-off fix for methodology line (Unicode apostrophe in "facility's")
with open('app.py', 'r', encoding='utf-8') as f:
    s = f.read()
old = "methodology = 'Case-mix (acuity) HPRD is the staffing level expected for this facility\u2019s acuity. Case-mix HPRD is a CMS metric for staffing levels based on resident acuity.'"
new = "methodology = 'Case-mix HPRD is a CMS metric for staffing levels based on resident acuity.'"
if old in s:
    s = s.replace(old, new)
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(s)
    print('Replaced')
else:
    print('Old not found')
