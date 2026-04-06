"""
handover/publisher.py

Publish handover artifacts to a GitHub Gist for easy sharing.
Pull a previously published handover from a Gist URL.

Uses the `gh` CLI (GitHub's official CLI) to create and view Gists.
Requires `gh` to be authenticated: run `gh auth login` once.

Phase 6 — Ecosystem & Developer Experience.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path


class PublisherError(Exception):
    """Raised when publishing or pulling fails."""


def _require_gh() -> None:
    """Raise PublisherError if gh CLI is not installed or not authenticated."""
    result = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise PublisherError(
            "GitHub CLI (gh) is not installed or not authenticated.\n"
            "Install: https://cli.github.com\n"
            "Then run: gh auth login"
        )


def publish(
    files: dict[str, str],
    description: str = "handover context",
    public: bool = False,
) -> str:
    """
    Create a GitHub Gist containing the given files and return its URL.

    Args:
        files: Dict mapping filename → content strings to publish.
        description: Gist description shown on GitHub.
        public: If True, create a public Gist. Defaults to secret.

    Returns:
        The Gist URL, e.g. 'https://gist.github.com/user/abc123'.

    Raises:
        PublisherError: If gh CLI is unavailable or the Gist creation fails.
    """
    _require_gh()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        paths: list[str] = []
        for filename, content in files.items():
            p = tmp / filename
            p.write_text(content, encoding="utf-8")
            paths.append(str(p))

        cmd = ["gh", "gist", "create"] + paths + ["--desc", description]
        if public:
            cmd.append("--public")

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise PublisherError(f"gh gist create failed:\n{result.stderr.strip()}")

        # gh prints the Gist URL on stdout
        url = result.stdout.strip()
        if not url.startswith("https://"):
            raise PublisherError(f"Unexpected output from gh gist create: {result.stdout!r}")
        return url


def pull(gist_url: str, output_dir: Path) -> list[Path]:
    """
    Download all files from a GitHub Gist and write them to output_dir.

    Args:
        gist_url: Full Gist URL or just the Gist ID.
        output_dir: Directory to write the downloaded files.

    Returns:
        List of Path objects for each written file.

    Raises:
        PublisherError: If gh CLI is unavailable or the Gist cannot be fetched.
    """
    _require_gh()

    # Extract the Gist ID from the URL
    gist_id = _extract_gist_id(gist_url)

    # Get the Gist metadata as JSON
    result = subprocess.run(
        ["gh", "api", f"gists/{gist_id}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise PublisherError(f"Failed to fetch Gist {gist_id}:\n{result.stderr.strip()}")

    try:
        gist_data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise PublisherError(f"Invalid JSON from gh api: {e}") from e

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for filename, file_info in gist_data.get("files", {}).items():
        content = file_info.get("content", "")
        out_path = output_dir / filename
        out_path.write_text(content, encoding="utf-8")
        written.append(out_path)

    if not written:
        raise PublisherError(f"No files found in Gist {gist_id}.")

    return written


def _extract_gist_id(url_or_id: str) -> str:
    """
    Extract the Gist ID from a full URL or return as-is if already an ID.

    Handles:
      https://gist.github.com/username/abc123def456
      https://gist.github.com/abc123def456
      abc123def456
    """
    # Try to extract the last path segment (the hash)
    match = re.search(r"/([0-9a-f]{20,})", url_or_id)
    if match:
        return match.group(1)
    # If no URL pattern, assume it's already an ID
    if re.match(r"^[0-9a-f]{20,}$", url_or_id):
        return url_or_id
    raise PublisherError(
        f"Could not extract Gist ID from: {url_or_id!r}\n"
        "Expected a full Gist URL or a 20+ character hex ID."
    )
