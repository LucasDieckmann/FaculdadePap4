import os
import csv

for name in sorted(os.listdir('.')):
    if not name.lower().endswith('.csv'):
        continue
    print(f'FILE: {name}')
    try:
        with open(name, newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if i >= 3:
                    break
                print('  ' + ' | '.join(row[:12]))
    except Exception as e:
        print('  ERROR:', e)
