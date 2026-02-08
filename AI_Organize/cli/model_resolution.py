from pathlib import Path
import json


def resolve_ollama_model(settings: dict, project_root: Path) -> str:
    ai_settings = settings.setdefault("ai", {})
    model = ai_settings.get("model")

    try:
        from akinus.ai.ollama import list_models
        available = list_models()
    except Exception:
        available = []

    if model and model in available:
        return model

    print("⚠️  Ollama model not configured or unavailable.")
    print("Available models:")
    for m in sorted(available):
        print(f"  - {m}")

    while True:
        choice = input("Enter Ollama model to use: ").strip()
        if choice in available:
            break
        print("❌ Model not found. Try again.")

    # Persist choice
    ai_settings["model"] = choice
    settings_path = project_root / "data" / "settings.json"
    settings_path.parent.mkdir(exist_ok=True)

    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

    print(f"✅ Saved Ollama model: {choice}")
    return choice
