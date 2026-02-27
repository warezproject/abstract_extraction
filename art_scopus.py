"""Project entrypoint.

This thin wrapper keeps the top-level script simple and delegates all runtime
logic to ``art_scopus_lib.cli.main``.
"""

from art_scopus_lib.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
