#!/usr/bin/env bash
set -e

if [ ! -f "pyproject.toml" ]; then
    echo "Error: pyproject.toml not found. Run this script from the project root."
    exit 1
fi

if [ ! -d ".git" ]; then
    echo "Error: .git directory not found. Initialize git repo or clone properly."
    exit 1
fi

if [ -z "$1" ]; then
    echo "Usage: $0 <new_project_name>"
    exit 1
fi

# Extract current project name from pyproject.toml ([project] name field)
OLD_NAME=$(sed -nE 's/^name\s*=\s*"(.*)"/\1/p' pyproject.toml | head -1)

if [ -z "$OLD_NAME" ]; then
    echo "Error: Could not find 'name' in pyproject.toml [project] section."
    exit 1
fi

echo "Current project name detected: '$OLD_NAME'"

# Sanitize new project name: replace hyphens with underscores
RAW_NEW_NAME="$1"
NEW_NAME="${RAW_NEW_NAME//-/_}"

if [ "$RAW_NEW_NAME" != "$NEW_NAME" ]; then
    echo "⚠️  Hyphens in new project name replaced with underscores for Python compatibility."
    echo "    Original: $RAW_NEW_NAME"
    echo "    Using:    $NEW_NAME"
fi

echo "Preparing to rename project from '$OLD_NAME' to '$NEW_NAME'..."

# 1. Rename package folder (if it exists)
if [ -d "$OLD_NAME" ]; then
    mv "$OLD_NAME" "$NEW_NAME"
    echo "📁 Renamed package folder."
else
    echo "⚠️ Package folder '$OLD_NAME' not found, skipping rename folder."
fi

# 2. Find all text files containing OLD_NAME, count occurrences, print summary
echo "🔍 Scanning files for occurrences of '$OLD_NAME'..."

declare -A files_to_modify=()

while IFS= read -r -d '' file; do
    mimetype=$(file --mime-type -b "$file")
    if [[ $mimetype == text/* ]]; then
        count=$(grep -o "$OLD_NAME" "$file" | wc -l || echo 0)
        if [ "$count" -gt 0 ]; then
            files_to_modify["$file"]=$count
        fi
    fi
done < <(find . -type f -not -path "./.git/*" -print0)

if [ ${#files_to_modify[@]} -eq 0 ]; then
    echo "✅ No occurrences of '$OLD_NAME' found in any text files. Nothing to replace."
    exit 0
fi

echo "The following files contain occurrences of '$OLD_NAME':"
for file in "${!files_to_modify[@]}"; do
    echo "  $file — ${files_to_modify[$file]} occurrence(s)"
done

echo -n "Proceed with replacing all occurrences of '$OLD_NAME' with '$NEW_NAME'? [y/N]: "
read -r answer
if [[ ! "$answer" =~ ^[Yy]$ ]]; then
    echo "❌ Aborting without making any changes."
    exit 0
fi

# 3. Perform replacements in all listed files
echo "🔄 Replacing occurrences in files..."
for file in "${!files_to_modify[@]}"; do
    sed -i "s/$OLD_NAME/$NEW_NAME/g" "$file"
    echo "  Updated $file (${files_to_modify[$file]} replacements)"
done

# 4. Stage all changes
git add .

# 5. Commit changes
git commit -m "Rename project from $OLD_NAME to $NEW_NAME"

# 6. Push changes
current_branch=$(git rev-parse --abbrev-ref HEAD)
git push origin "$current_branch"

echo "✅ Project renamed, committed, and pushed to branch '$current_branch'."

# 7. Self-delete
rm -- "$0"
