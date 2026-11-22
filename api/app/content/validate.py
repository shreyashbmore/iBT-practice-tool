"""CLI: python -m app.content.validate — checks every YAML set and prints a summary."""
import sys

from .bank import ContentError, load_dir, load_forms


def main() -> int:
    try:
        sets = load_dir()
    except ContentError as e:
        print(e)
        return 1
    for s in sets.values():
        print(f"✓ {s.id:<16} {s.task:<22} {len(s.items):>2} item(s)")
    print(f"{len(sets)} set(s) valid")
    try:
        fs = load_forms(sets=sets)
    except ContentError as e:
        print(e)
        return 1
    for f in fs.values():
        print(f"✓ form {f.id}: router {f.router} → lower {f.lower} / upper {f.upper}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
