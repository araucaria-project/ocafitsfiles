#!/usr/bin/env python3
"""Quick-test helper: render a download script from stdin data.

Usage (from project root):

    echo "file1.fits extra_col" | python -m ocafitsfiles.download_script \\
        --token TEST

    cat my_filelist.txt | python -m ocafitsfiles.download_script \\
        --token SECRET > out.sh

This is a thin wrapper around render_download_script() intended for
quick template iteration without needing the separate CLI project.
"""

import argparse
import sys

from ocafitsfiles._download import render_download_script, DEFAULT_API_ENDPOINT


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ocafitsfiles.download_script",
        description="Render a download script (reads data block from stdin, writes script to stdout).",
    )
    parser.add_argument(
        "--token", required=True,
        help="API bearer token to embed.",
    )
    parser.add_argument(
        "--endpoint", default=DEFAULT_API_ENDPOINT,
        help="Base API endpoint (default: %(default)s).",
    )
    parser.add_argument(
        "--expires-in", type=int, default=604_800,
        help="Presigned URL validity in seconds (default: %(default)s = 7 days).",
    )
    parser.add_argument(
        "--dl-timeout", type=int, default=300,
        help="curl/wget transfer timeout in seconds (default: %(default)s).",
    )
    args = parser.parse_args()

    data = sys.stdin.read()

    script = render_download_script(
        data,
        api_endpoint=args.endpoint,
        api_token=args.token,
        expires_in=args.expires_in,
        dl_timeout=args.dl_timeout,
    )
    sys.stdout.write(script)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
