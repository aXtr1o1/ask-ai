import os
import glob

files = glob.glob('app/api/routes/*.py')
for f in files:
    if f.endswith('__init__.py') or f.endswith('query_search_fallback.py') or f.endswith('app_endpoints.py'):
        continue
    
    with open(f, 'r') as file:
        lines = file.readlines()
        
    logger_name = "logger_sb" if "sb.py" in f else "logger"
    log_line = f'payloadlog: filter values: %s", {k: v for k, v in req.model_dump().items() if v not in (None, "")}'
    
    new_lines = []
    for line in lines:
        new_lines.append(line)
        if 'conn = get_pool()' in line:
            indent = line[:len(line) - len(line.lstrip())]
            new_lines.append(f'{indent}{logger_name}.info("{log_line})\n')
            
    with open(f, 'w') as file:
        file.writelines(new_lines)
