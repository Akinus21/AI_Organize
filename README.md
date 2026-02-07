# uv_base
Base template for a simple Python project using [uv](https://docs.astral.sh/uv/).

## Description
A simple CLI example that runs instantly after cloning, or can be installed globally for use anywhere.

---

## 🚀 Run Without Installing
Clone the repository and run the project directly with `uv`:

```bash
git clone https://github.com/YOURNAME/uv_base.git
cd uv_base
uv run uv_base
```
This will:

Create an isolated virtual environment in .venv (if it doesn’t already exist)

Install any dependencies from pyproject.toml

Run the uv_base CLI

🌍 Install Globally
If you want to use the CLI anywhere on your system without uv run:

```bash
git clone https://github.com/YOURNAME/uv_base.git
cd uv_base
uv pip install .
```
Then run:

```bash
uv_base
```
from any directory.

🗑️ Uninstall
```bash
uv pip uninstall uv_base
```
------