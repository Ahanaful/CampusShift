"""Create a source-only archive from an allowlist; never includes .env or databases."""
from pathlib import Path
import tarfile


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / ".local/campusshift-backend.tar.gz"
    output.parent.mkdir(exist_ok=True)
    directories = ("backend/app", "backend/alembic", "scheduler", "infrastructure/runtime")
    files = [root / path for path in ("backend/main.py", "backend/requirements.txt", "backend/alembic.ini", "pyproject.toml", "scripts/configure_server.py", "scripts/deploy_backend.sh", "scripts/database_backup.sh", "scripts/sqlite_backup.py")]
    for directory in directories:
        files.extend(path for path in (root / directory).rglob("*") if path.is_file() and "__pycache__" not in path.parts and "tests" not in path.parts and path.suffix in {".py", ".mako", ".json", ".conf", ".service", ".timer"})
    with tarfile.open(output, "w:gz") as archive:
        for path in sorted(set(files)):
            if path.is_symlink():
                raise SystemExit("Refusing symbolic links in the source archive")
            archive.add(path, arcname=path.relative_to(root).as_posix(), recursive=False)
    print(output)


if __name__ == "__main__":
    main()
