# SplitRight AI Usage Documentation

This document logs details of the AI tools utilized during the development of SplitRight, including key prompts and three cases where AI assumptions were corrected.

---

## 1. AI Tools Used

- **Agentic IDE Assistant:** Antigravity (Google DeepMind), powered by Gemini 3.5 Flash.
- **Role:** Pair programmer executing environment setups, file creations, backend route definitions, unit testing, and CSS stylings.

---

## 2. Key Prompts

- *Bootstrap Plan:* "Build and deploy a full-stack shared expenses web app called 'SplitRight' with Flask backend, React frontend, SQLite database..."
- *CSV Importer Prompt:* "Write a CSV importer that checks date formats, duplicate rows, missing currency, negative numbers, name variations, guest creation, and time boundaries for flatmates Meera and Sam..."
- *Debt Minimization Prompt:* "Implement a greedy debt minimization algorithm in python to reduce total transaction settlement counts."

---

## 3. 3 Cases Where AI Was Wrong & What Was Fixed

### Case 1: React Input Value Typos
- **What AI did wrong:** Scaffolded the user registration name input field with:
  `value={name => setAuthName(name.target.value)}`
  This was an invalid React input value expression (a function instead of a state string), which threw warning/error states and blocked typing.
- **What was fixed:** Replaced the typo with the correct state variable:
  `value={authName}`
  This resolved input reactivity.

### Case 2: PowerShell Operator Mismatch
- **What AI did wrong:** Attempted to chain terminal commands using the bash operator `&&` (e.g. `git add . && git commit`). Because the local shell environment is Windows PowerShell, it crashed with parser errors.
- **What was fixed:** Substituted the commands using PowerShell syntax operators (`;`) to successfully execute git and npm operations in sequence.

### Case 3: Global Python Dependency Resolution
- **What AI did wrong:** Attempted to run the Flask application server and Pytest suites via the global command `python app.py`. This failed immediately because dependencies are isolated in the local `.venv` environment, not global.
- **What was fixed:** Explicitly invoked the virtual environment interpreter executable:
  `.\venv\Scripts\python.exe app.py`
  and
  `..\venv\Scripts\pytest -s`
  This ensured imports like `flask`, `jwt`, and `pytest` resolved cleanly.
