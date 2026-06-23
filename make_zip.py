import zipfile
import os

exclude_dirs = {'venv', '.venv', '__pycache__', '.git', '.vscode', 'v2_backup', 'media'}

with zipfile.ZipFile('deploy_quiz.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file.endswith('.zip') or file.endswith('.pyc'):
                continue
            file_path = os.path.join(root, file)
            zipf.write(file_path, os.path.relpath(file_path, '.'))

print("Zipping completed successfully.")
