# AI_Organize
Base template for a simple Python project using [uv](https://docs.astral.sh/uv/).

## Description
A simple CLI example that runs instantly after cloning, or can be installed globally for use anywhere.

---

## 🚀 Run Without Installing
Clone the repository and run the project directly with `uv`:

```bash
git clone https://github.com/YOURNAME/AI_Organize.git
cd AI_Organize
uv run AI_Organize
```
This will:

Create an isolated virtual environment in .venv (if it doesn’t already exist)

Install any dependencies from pyproject.toml

Run the AI_Organize CLI

🌍 Install Globally
If you want to use the CLI anywhere on your system without uv run:

```bash
git clone https://github.com/YOURNAME/AI_Organize.git
cd AI_Organize
uv pip install .
```
Then run:

```bash
AI_Organize
```
from any directory.

🗑️ Uninstall
```bash
uv pip uninstall AI_Organize
```
------