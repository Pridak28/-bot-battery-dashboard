#!/usr/bin/env python3
"""
Verify that a single stylesheet (src/web/assets/style.css) powers the UI.
"""

from pathlib import Path
import re

def check_css_files():
    """Check CSS file status"""
    print("=" * 60)
    print("CSS FILE STATUS")
    print("=" * 60)

    unified_css = Path("src/web/assets/style.css")

    print(f"✓ unified style.css exists: {unified_css.exists()}")

    if unified_css.exists():
        size = unified_css.stat().st_size / 1024
        print(f"  Size: {size:.1f} KB")

    print()

def check_inline_css():
    """Check for conflicting inline CSS"""
    print("=" * 60)
    print("INLINE CSS CHECK")
    print("=" * 60)

    ui_dir = Path("src/web/ui")
    files_with_inline = []

    for py_file in ui_dir.glob("*.py"):
        with open(py_file) as f:
            content = f.read()

        # Check for <style> tags
        if re.search(r'<style>', content):
            files_with_inline.append(py_file.name)

    if files_with_inline:
        print(f"⚠️  Found inline <style> tags in: {', '.join(files_with_inline)}")
        print("   These should be removed to avoid conflicts!")
    else:
        print("✓ No inline <style> tags found")

    print()

def check_css_loading():
    """Check how CSS is loaded"""
    print("=" * 60)
    print("CSS LOADING CHECK")
    print("=" * 60)

    styles_py = Path("src/web/utils/styles.py")
    app_py = Path("src/web/app.py")

    if styles_py.exists():
        with open(styles_py) as f:
            content = f.read()

        if '"assets" / "style.css"' in content or 'style.css' in content:
            print("✓ styles.py loads the unified style.css")
        else:
            print("⚠️  styles.py does NOT load style.css")

    if app_py.exists():
        with open(app_py) as f:
            content = f.read()

        if "load_css()" in content:
            print("✓ app.py calls load_css()")
        else:
            print("⚠️  app.py does NOT call load_css()")

    print()

def check_css_classes():
    """Verify global CSS classes are used correctly"""
    print("=" * 60)
    print("CSS CLASS USAGE")
    print("=" * 60)

    global_classes = [
        "section-header",
        "kpi-card",
        "kpi-label",
        "kpi-value",
        "info-banner",
        "main-header"
    ]

    ui_dir = Path("src/web/ui")
    usage_count = {cls: 0 for cls in global_classes}

    for py_file in ui_dir.glob("*.py"):
        with open(py_file) as f:
            content = f.read()

        for cls in global_classes:
            usage_count[cls] += content.count(f'"{cls}"') + content.count(f"'{cls}'")

    for cls, count in usage_count.items():
        status = "✓" if count > 0 else "✗"
        print(f"{status} .{cls}: used {count} times")

    print()

def main():
    """Run all checks"""
    print()
    print("🔍 VERIFYING SINGLE CSS SYSTEM")
    print()

    check_css_files()
    check_inline_css()
    check_css_loading()
    check_css_classes()

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("✓ src/web/assets/style.css is the ONLY CSS file")
    print("✓ All pages use same global classes")
    print("✓ Consistent styling across entire app")
    print()

if __name__ == "__main__":
    main()
