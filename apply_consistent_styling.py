#!/usr/bin/env python3
"""
Script to apply consistent professional styling across ALL UI modules
Removes emojis and applies section_header pattern
"""

import re
from pathlib import Path

# UI modules to update
UI_DIR = Path("src/web/ui")
MODULES = [
    "romanian_bm.py",
    "investment.py",
    "fr_energy_hedging.py",
    "market_comparison.py"
]

def update_file(filepath: Path):
    """Update a single file with consistent styling"""
    print(f"Processing {filepath.name}...")

    with open(filepath, 'r') as f:
        content = f.read()

    # Add import if not present
    if 'from src.web.utils.styles import' not in content:
        # Find the last import statement
        import_pattern = r'(from src\.web\.utils\.formatting import.*?\n)'
        replacement = r'\1from src.web.utils.styles import section_header, kpi_card, kpi_grid\n'
        content = re.sub(import_pattern, replacement, content)

    # Replace st.header/st.subheader with section_header
    # Pattern: st.header("text") or st.subheader("text")
    content = re.sub(
        r'st\.(header|subheader)\s*\(\s*"([^"]+)"\s*\)',
        lambda m: f'section_header("{m.group(2)}")',
        content
    )

    # Remove emojis from success/error/warning/info messages
    emoji_patterns = [
        (r'st\.success\s*\(\s*"[^"]*?(✅|🎯|💰|📊|📈)\s*', 'st.success("'),
        (r'st\.error\s*\(\s*"[^"]*?(❌|⚠️)\s*', 'st.error("'),
        (r'st\.warning\s*\(\s*"[^"]*?(⚠️|⚡)\s*', 'st.warning("'),
        (r'st\.info\s*\(\s*"[^"]*?(ℹ️|💡|📋)\s*', 'st.info("'),
    ]

    for pattern, replacement in emoji_patterns:
        content = re.sub(pattern, replacement, content)

    # Write back
    with open(filepath, 'w') as f:
        f.write(content)

    print(f"  ✓ Updated {filepath.name}")


def main():
    """Apply styling to all modules"""
    for module_name in MODULES:
        filepath = UI_DIR / module_name
        if filepath.exists():
            update_file(filepath)
        else:
            print(f"  ✗ {module_name} not found")

    print("\n✅ Styling applied to all modules!")


if __name__ == "__main__":
    main()
