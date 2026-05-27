import os

directory = 'c:/Users/lenovo/Desktop/college_pms_final_version'
search_text = 'ProjectInsight'
replace_text = 'ProjectInsight'

for root, dirs, files in os.walk(directory):
    for file in files:
        if file.endswith('.py') or file.endswith('.html'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            if search_text in content:
                print(f'Replacing in {filepath}')
                content = content.replace(search_text, replace_text)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
print('Done!')
