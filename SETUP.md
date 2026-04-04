Project Setup Guide
Project: Calendar Project
Author: Chris
Environment: Windows 10/11, Python 3.12.10, Git Bash, GitHub

This document outlines the full setup process for this project, including Python installation, environment configuration, Git initialisation, and repository setup.

🐍 1. Python Installation & Configuration
1.1 Install Python 3.12.10
Python was installed from the official Python.org Windows installer.

1.2 Ensure Python 3.12.10 is the Default Version
To make python point to 3.12.10:

Repaired the Python 3.12.10 installation

Updated PATH so that:

Code
C:\Users\pc\AppData\Local\Programs\Python\Python312\
C:\Users\pc\AppData\Local\Programs\Python\Python312\Scripts\
appear before any older Python versions.

1.3 Verify Installation
bash
python --version
py --list
where python
Expected output:

python → Python 3.12.10

py -3.12 launches Python 3.12.10

🧪 2. Virtual Environment Setup
2.1 Create the venv
bash
python -m venv venv
2.2 Activate the venv
bash
source venv/Scripts/activate
2.3 Confirm venv is active
Your terminal should show:

Code
(venv)
📁 3. Project Structure (Initial)
Code
calendar_project/
│
├── app/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── manage.py
├── .gitignore
└── venv/   (ignored)

🧹 4. .gitignore Configuration
A .gitignore file was created to prevent unnecessary files from being committed.

Contents:

Code
venv/
__pycache__/
*.pyc
.env
This ensures:

Virtual environment is not committed

Python cache files are ignored

Environment variables remain private

🌱 5. Git Initialisation
5.1 Initialise Git
bash
git init
5.2 Stage Files
bash
git add .
5.3 Commit
bash
git commit -m "Initial commit with .gitignore"

🌐 6. GitHub Repository Setup
6.1 Add the Correct Remote
bash
git remote add origin https://github.com/mcevoycd/calendar_project.git
Verify:

bash
git remote -v
6.2 Rename Branch to main
bash
git branch -M main
6.3 Push to GitHub
bash
git push -u origin main
🧪 7. Verification Commands
Useful checks:

bash
git status
git remote -v
python --version
py --list
where python
