"""Publish a validated local Teacher Companion to an editable Google Doc."""

from __future__ import annotations

import argparse
from pathlib import Path

from curriculum.intelligence.publishing import write_publishing_metadata
from renderer.google_docs_publisher import GoogleDocsPublisher
from schemas.teaching_package_schema import StructuredTeachingPackage


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--credentials", default="credentials.json")
    parser.add_argument("--token", default="token.json")
    args = parser.parse_args()
    path = Path(args.input)
    try:
        package = StructuredTeachingPackage.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        result = GoogleDocsPublisher(
            credentials_path=args.credentials,
            token_path=args.token,
        ).publish(package)
        write_publishing_metadata(path.parent, google_doc=result)
    except (OSError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    print(f"Google Doc: {result['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
