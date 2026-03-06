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
    4 - self-authenticating: embed username instead of token; script
        handles login, password acquisition (-p / $OCADB_PASSWORD /
        interactive prompt), token refresh, and 401 retry
"""

import json
import re
from string import Template
from importlib.resources import files
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


_TEMPLATE_TEXT: str = (
    files("ocafitsfiles._templates").joinpath("download.sh").read_text()
)

# Extract template-version from the rendered template header
_VERSION_MATCH = re.search(r'^# template-version:\s*(\d+)', _TEMPLATE_TEXT, re.MULTILINE)
TEMPLATE_VERSION: int = int(_VERSION_MATCH.group(1)) if _VERSION_MATCH else 0

# Default OCA API endpoint
DEFAULT_API_ENDPOINT = "https://api.ocadb.space/api/v1/observations"
DEFAULT_AUTH_ENDPOINT = "https://api.ocadb.space/api/v1/auth/plaintoken/"


def fetch_user_token(
    username: str,
    password: str,
    *,
    auth_endpoint: str = DEFAULT_AUTH_ENDPOINT,
    timeout: int = 30,
) -> str:
    """Fetch a bearer token for a user from the OCA auth endpoint.

    The endpoint is expected to return JSON with an ``access_token`` field.
    """
    payload = urlencode(
        {
            "username": username,
            "password": password,
            "grant_type": "password",
        }
    ).encode("utf-8")

    req = Request(
        auth_endpoint,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": "Bearer",
        },
    )

    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        raise RuntimeError(f"Auth failed: HTTP {exc.code} {detail}".strip()) from exc
    except URLError as exc:
        raise RuntimeError(f"Auth failed: {exc.reason}") from exc

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Auth failed: non-JSON response") from exc

    token = data.get("access_token") if isinstance(data, dict) else None
    if not isinstance(token, str) or not token.strip():
        raise RuntimeError("Auth failed: missing access_token in response")

    return token.strip()


def render_download_script(
    data_block: str,
    *,
    username: str,
    api_endpoint: str = DEFAULT_API_ENDPOINT,
    auth_endpoint: str = DEFAULT_AUTH_ENDPOINT,
    expires_in: int = 604_800,
    dl_timeout: int = 300,
    generated_date: str | None = None,
) -> str:
    """Render a self-sufficient POSIX sh download/check script.

    The generated script authenticates on its own (password via CLI arg,
    env var, or interactive prompt) and manages token refresh automatically.

    Parameters:
        data_block:      Text to embed as the file list.
                         Each line's first whitespace-separated column is the
                         object key / filename.  Lines starting with '#' are
                         treated as comments by the generated script.
        username:        OCADB username to embed in the script.
        api_endpoint:    Base API URL (default: OCA production endpoint).
                         The script appends /by-filename/{key}/plainurl.
        auth_endpoint:   Authentication URL (default: OCA plaintoken endpoint).
        expires_in:      Presigned URL validity in seconds (default: 604800 = 7 days,
                         the maximum allowed by S3-compatible stores).
        dl_timeout:      curl/wget transfer timeout in seconds (default: 300).
        generated_date:  ISO date string for the script header (default: today).

    Returns:
        Complete shell script as a string (includes trailing newline).
    """
    import datetime

    if generated_date is None:
        generated_date = datetime.date.today().isoformat()

    # Count active (non-blank, non-comment) lines for the header
    n_files = sum(
        1 for line in data_block.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )

    safe_endpoint = api_endpoint.rstrip("/").replace('"', '\\"')
    safe_auth = auth_endpoint.replace('"', '\\"')
    safe_username = username.replace('"', '\\"')

    script = Template(_TEMPLATE_TEXT).substitute(
        api_endpoint=safe_endpoint,
        auth_endpoint=safe_auth,
        username=safe_username,
        expires_in=expires_in,
        dl_timeout=dl_timeout,
        generated_date=generated_date,
        n_files=n_files,
        data_block=data_block.rstrip("\n"),
    )

    if not script.endswith("\n"):
        script += "\n"

    return script

