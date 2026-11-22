"""Repository guard: nothing that must stay out of git is ever tracked.

Test case TC-33. Requirement NFR-08: no secrets, datasets, rendered images,
model weights or private docs in the public code repository.

The guard reads the list of tracked files from `git ls-files`, so it checks
exactly what would be pushed, not whatever happens to sit in the folder.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

# Any single tracked file larger than this is almost certainly data or weights.
MAXIMUM_TRACKED_FILE_BYTES = 1_000_000

# Model weights, archives and raw arrays never belong in git, anywhere.
FORBIDDEN_EXTENSIONS = {
    ".pt", ".pth", ".ckpt", ".safetensors", ".onnx",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".npy", ".npz", ".h5", ".parquet", ".lmdb",
}

# Images and fonts are allowed only as small test fixtures or README assets.
RESTRICTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".ttf", ".otf"}
ALLOWED_FOLDERS_FOR_RESTRICTED_FILES = ("tests/fixtures/", "assets/")

# Secret patterns. Each is written so that this file itself does not match it.
SECRET_PATTERNS = {
    "Hugging Face token": re.compile(r"hf_[A-Za-z0-9]{30,}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "filled-in secret variable": re.compile(
        r"^(HF_TOKEN|WANDB_API_KEY|API_KEY|SECRET_KEY)\s*=\s*\S+", re.MULTILINE
    ),
}


def list_tracked_files(repository_root: Path) -> list[str]:
    """Return every path git tracks (including staged files), with forward slashes."""
    git_result = subprocess.run(
        ["git", "ls-files"],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in git_result.stdout.splitlines() if line]


@pytest.fixture(scope="module")
def tracked_files(repository_root: Path) -> list[str]:
    """Tracked file paths, or skip the module when git or the .git folder is missing."""
    if shutil.which("git") is None or not (repository_root / ".git").exists():
        pytest.skip("git or the .git folder is not available here")
    return list_tracked_files(repository_root)


def test_no_tracked_file_is_too_large(repository_root: Path, tracked_files: list[str]):
    oversized_files = [
        file_path
        for file_path in tracked_files
        if (repository_root / file_path).stat().st_size > MAXIMUM_TRACKED_FILE_BYTES
    ]
    assert oversized_files == [], (
        f"Files over {MAXIMUM_TRACKED_FILE_BYTES} bytes: {oversized_files}"
    )


def test_no_weights_archives_or_arrays_are_tracked(tracked_files: list[str]):
    forbidden_files = [
        file_path
        for file_path in tracked_files
        if Path(file_path).suffix.lower() in FORBIDDEN_EXTENSIONS
    ]
    assert forbidden_files == [], f"Weights, archives or arrays tracked: {forbidden_files}"


def test_images_and_fonts_only_in_fixtures_or_assets(tracked_files: list[str]):
    misplaced_files = [
        file_path
        for file_path in tracked_files
        if Path(file_path).suffix.lower() in RESTRICTED_EXTENSIONS
        and not file_path.startswith(ALLOWED_FOLDERS_FOR_RESTRICTED_FILES)
    ]
    assert misplaced_files == [], (
        f"Images or fonts outside tests/fixtures/ or assets/: {misplaced_files}"
    )


def test_env_file_and_private_docs_are_not_tracked(tracked_files: list[str]):
    # .env.example (empty values) is allowed; the real .env never is.
    leaked_files = [
        file_path
        for file_path in tracked_files
        if Path(file_path).name == ".env" or file_path.startswith("docs/")
    ]
    assert leaked_files == [], f".env or private docs tracked: {leaked_files}"


def test_no_secrets_in_tracked_text_files(repository_root: Path, tracked_files: list[str]):
    secrets_found = []
    for file_path in tracked_files:
        try:
            file_text = (repository_root / file_path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary fixtures cannot hold a pasted secret in readable form
        for secret_name, secret_pattern in SECRET_PATTERNS.items():
            if secret_pattern.search(file_text):
                # Report where, never the secret itself.
                secrets_found.append(f"{secret_name} in {file_path}")
    assert secrets_found == [], f"Possible secrets: {secrets_found}"
