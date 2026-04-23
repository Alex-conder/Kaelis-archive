import re
from pathlib import Path

files = [
    'api/routes/intent.py',
    'api/routes/knowledge_graph.py',
    'api/routes/reports.py',
    'api/routes/team.py',
    'api/routes/system.py',
    'api/routes/symbols.py',
    'api/routes/omics.py',
]

pattern = re.compile(
    r'    class Config:\s*\n'
    r'        """Pydantic configuration"""\s*\n'
    r'        json_encoders = \{\s*\n'
    r'            datetime: lambda v: v\.isoformat\(\)\s*\n'
    r'        \}'
)
replacement = '    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})'

for f in files:
    p = Path(f)
    if not p.exists():
        print('SKIP', f)
        continue
    content = p.read_text(encoding='utf-8')
    if 'ConfigDict' not in content:
        content = content.replace('from pydantic import BaseModel', 'from pydantic import BaseModel, ConfigDict')
    content = pattern.sub(replacement, content)
    p.write_text(content, encoding='utf-8')
    print('FIXED', f)
print('Done')
