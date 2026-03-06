"""Download script generator.

Renders a self-sufficient POSIX sh script with an embedded __DATA__ table.
The generated script supports listing, checking, and downloading files
via presigned URLs from an object store API.

Template version history:
    1 - initial version (generic ?key= query param)
    2 - match real OCA API: /by-filename/{key}/plainurl?expires_in=,
        separate expires_in (presigned URL validity) from dl_timeout
        (curl/wget transfer timeout)
    3 - fix subshell counter scoping (pipe | while loses variables);
        use temp-file counters for correct ok/fail/skip summary
"""

import re
from string import Template
from importlib.resources import files


_TEMPLATE_TEXT: str = (
    files("ocafitsfiles._templates").joinpath("download.sh").read_text()
)

# Extract template-version from the rendered template header
_VERSION_MATCH = re.search(r'^# template-version:\s*(\d+)', _TEMPLATE_TEXT, re.MULTILINE)
TEMPLATE_VERSION: int = int(_VERSION_MATCH.group(1)) if _VERSION_MATCH else 0

# Default OCA API endpoint
DEFAULT_API_ENDPOINT = "https://api.ocadb.space/api/v1/observations"


def render_download_script(
    data_block: str,
    *,
    api_endpoint: str = DEFAULT_API_ENDPOINT,
    api_token: str,
    expires_in: int = 604_800,
    dl_timeout: int = 300,
) -> str:
    """Render a self-sufficient POSIX sh download/check script.

    Parameters:
        data_block:    Text to embed after __DATA__.
                       Each line's first whitespace-separated column is the
                       object key / filename.  Lines starting with '#' are
                       treated as comments by the generated script.
        api_endpoint:  Base API URL (default: OCA production endpoint).
                       The script appends /by-filename/{key}/plainurl.
        api_token:     Bearer token for the API.
        expires_in:    Presigned URL validity in seconds (default: 604800 = 7 days,
                       the maximum allowed by S3-compatible stores).
        dl_timeout:    curl/wget transfer timeout in seconds (default: 300).

    Returns:
        Complete shell script as a string (includes trailing newline).
    """
    safe_endpoint = api_endpoint.rstrip("/").replace('"', '\\"')
    safe_token = api_token.replace('"', '\\"')

    script = Template(_TEMPLATE_TEXT).substitute(
        api_endpoint=safe_endpoint,
        api_token=safe_token,
        expires_in=expires_in,
        dl_timeout=dl_timeout,
        data_block=data_block.rstrip("\n"),
    )

    if not script.endswith("\n"):
        script += "\n"

    return script

