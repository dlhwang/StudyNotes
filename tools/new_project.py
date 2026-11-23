"""이 틀을 복사해 새 Agent 프로젝트를 만든다.

    python tools/new_project.py <새 폴더> <패키지 이름>
    예: python tools/new_project.py D:\\workspace\\shop\\ai-agent shop_agent

하는 일
1. 이 폴더를 <새 폴더>로 복사한다(.venv, 캐시, .env 는 빼고).
2. 패키지 이름 ``study_notes`` → <패키지 이름>, 환경 변수 접두어 ``STUDY_NOTES_`` → <패키지 이름 대문자>_,
   배포 이름 ``study-notes`` → <패키지 이름의 _를 -로>.
3. 예시 Agent(agents/tasks)는 그대로 둔다. 자기 Agent를 만든 뒤 지운다 (docs/02 §6).
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".venv", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache", ".env"}
TEXT_SUFFIXES = {".py", ".md", ".toml", ".json", ".ini", ".mako", ".yaml", ".yml", ".example", ".txt", ""}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write(__doc__ or "")
        return 2
    dest, package = Path(argv[0]).resolve(), argv[1]
    if not re.fullmatch(r"[a-z][a-z0-9_]*", package):
        sys.stderr.write("패키지 이름은 영문 소문자·숫자·밑줄만 씁니다. 예: shop_agent\n")
        return 2
    if dest.exists() and any(dest.iterdir()):
        sys.stderr.write(f"{dest} 가 비어 있지 않습니다\n")
        return 2

    shutil.copytree(ROOT, dest, ignore=lambda _d, names: [n for n in names if n in SKIP or n.endswith(".egg-info")])
    (dest / "src" / "study_notes").rename(dest / "src" / package)

    prefix = package.upper() + "_"
    dist = package.replace("_", "-")
    for path in dest.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        new = text.replace("study_notes", package).replace("STUDY_NOTES_", prefix).replace("study-notes", dist)
        if new != text:
            path.write_text(new, encoding="utf-8", newline="")
    sys.stdout.write(f"만들었습니다: {dest}\n다음: docs/02-개발-가이드.md §1부터\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
