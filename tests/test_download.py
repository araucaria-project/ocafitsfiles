import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from ocafitsfiles import (
    DEFAULT_API_ENDPOINT,
    DEFAULT_AUTH_ENDPOINT,
    TEMPLATE_VERSION,
    fetch_user_token,
    render_download_script,
)


class TestRenderDownloadScript(unittest.TestCase):

    def _render(self, **kwargs):
        defaults = dict(
            data_block="file1.fits  extra\nfile2.fits  extra2",
            username="testuser",
            api_endpoint="https://api.ocadb.space/api/v1/files/by-file-name",
            auth_endpoint="https://api.ocadb.space/api/v1/auth/plaintoken/",
            expires_in=3600,
            dl_timeout=60,
            generated_date="2026-03-06",
        )
        defaults.update(kwargs)
        return render_download_script(**defaults)

    def test_shebang(self):
        script = self._render()
        self.assertTrue(script.startswith("#!/bin/sh\n"))

    def test_template_version_in_header(self):
        script = self._render()
        self.assertIn("# template-version:", script)

    def test_template_version_constant(self):
        self.assertIsInstance(TEMPLATE_VERSION, int)
        self.assertGreaterEqual(TEMPLATE_VERSION, 6)

    def test_endpoint_substituted(self):
        script = self._render(api_endpoint="https://api.ocadb.space/api/v1/files/by-file-name")
        self.assertIn('API_ENDPOINT="https://api.ocadb.space/api/v1/files/by-file-name"', script)

    def test_endpoint_trailing_slash_stripped(self):
        script = self._render(api_endpoint="https://api.ocadb.space/api/v1/files/by-file-name/")
        self.assertIn('API_ENDPOINT="https://api.ocadb.space/api/v1/files/by-file-name"', script)

    def test_username_substituted(self):
        script = self._render(username="observer")
        self.assertIn('USERNAME="observer"', script)

    def test_auth_endpoint_substituted(self):
        script = self._render(auth_endpoint="https://api.ocadb.space/api/v1/auth/plaintoken/")
        self.assertIn('AUTH_ENDPOINT="https://api.ocadb.space/api/v1/auth/plaintoken/"', script)

    def test_expires_in_substituted(self):
        script = self._render(expires_in=604800)
        self.assertIn('EXPIRES_IN="604800"', script)

    def test_dl_timeout_substituted(self):
        script = self._render(dl_timeout=42)
        self.assertIn('DL_TIMEOUT="42"', script)

    def test_generated_date_in_header(self):
        script = self._render(generated_date="2026-03-06")
        self.assertIn("2026-03-06", script)

    def test_n_files_computed(self):
        script = self._render(data_block="a.fits\nb.fits\n# comment\n\nc.fits\n")
        # 3 active lines (a.fits, b.fits, c.fits)
        self.assertIn("3 file(s)", script)

    def test_n_files_in_header_comment(self):
        script = self._render(data_block="x.fits\ny.fits\n")
        self.assertIn("# User: testuser | Date: 2026-03-06 | Files: 2", script)

    def test_data_block_embedded(self):
        script = self._render(data_block="alpha.fits\nbeta.fits\n")
        self.assertIn("\n__DATA__\nalpha.fits\nbeta.fits", script)

    def test_no_raw_placeholders_remain(self):
        """Ensure no $word placeholders are left unsubstituted."""
        script = self._render()
        for ph in ("$api_endpoint", "$auth_endpoint", "$username",
                    "$expires_in", "$dl_timeout", "$data_block",
                    "$generated_date", "$n_files"):
            self.assertNotIn(ph, script)

    def test_trailing_newline(self):
        script = self._render()
        self.assertTrue(script.endswith("\n"))

    def test_empty_data_block(self):
        script = self._render(data_block="")
        self.assertIn("\n__DATA__\n", script)
        self.assertIn("0 file(s)", script)

    def test_quotes_in_username_escaped(self):
        script = self._render(username='user"name')
        self.assertIn(r'user\"name', script)

    def test_fetch_url_pattern(self):
        """Generated script builds /files/by-file-name/{key}/plainurl?expires_in= URLs."""
        script = self._render()
        self.assertIn("/files/by-file-name/", script)
        self.assertIn("/plainurl?expires_in=", script)

    def test_default_endpoint(self):
        self.assertEqual(DEFAULT_API_ENDPOINT, "https://api.ocadb.space/api/v1/files/by-file-name")

    def test_no_hardcoded_token(self):
        """Template must NOT contain a hardcoded API_TOKEN assignment."""
        script = self._render()
        # API_TOKEN="" is the runtime init - that's fine.
        # Ensure no API_TOKEN="<actual token>" appears.
        for line in script.splitlines():
            if line.startswith('API_TOKEN=') and line != 'API_TOKEN=""':
                self.fail(f"Hardcoded token found: {line}")

    def test_upfront_login_block_present_for_download_and_check(self):
        script = self._render()
        self.assertIn('if [ "$$MODE" = "check" ] || [ "$$MODE" = "download" ]; then', script)
        self.assertIn('  ensure_tools', script)
        self.assertIn('  resolve_password', script)
        self.assertIn('  login || { err "ERROR: initial login failed"; exit 1; }', script)

    def test_password_prompt_reads_from_tty(self):
        script = self._render()
        self.assertIn('if [ ! -r /dev/tty ]; then', script)
        self.assertIn('IFS= read -r PASSWORD < /dev/tty', script)
        self.assertIn('stty -echo < /dev/tty 2>/dev/null', script)

    def test_skipped_lines_are_printed(self):
        script = self._render()
        self.assertIn("printf 'Downloading %s ... SKIPPED", script)

    def test_generated_date_defaults_to_today(self):
        import datetime
        script = render_download_script(
            "f.fits", username="u",
        )
        self.assertIn(datetime.date.today().isoformat(), script)

    def test_not_found_message_present(self):
        script = self._render()
        self.assertIn("NOT FOUND", script)

class _FakeResponse:
    def __init__(self, payload: str):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestFetchUserToken(unittest.TestCase):
    def test_default_auth_endpoint_constant(self):
        self.assertEqual(DEFAULT_AUTH_ENDPOINT, "https://api.ocadb.space/api/v1/auth/plaintoken/")

    @patch("ocafitsfiles._download.urlopen")
    def test_fetch_user_token_success(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse('{"access_token": "abc123"}')

        token = fetch_user_token("observer", "secret")

        self.assertEqual(token, "abc123")
        args, kwargs = mock_urlopen.call_args
        req = args[0]
        self.assertEqual(req.full_url, DEFAULT_AUTH_ENDPOINT)
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(kwargs["timeout"], 30)

    @patch("ocafitsfiles._download.urlopen")
    def test_fetch_user_token_http_error(self, mock_urlopen):
        err = HTTPError(
            url=DEFAULT_AUTH_ENDPOINT,
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"detail": "bad credentials"}'),
        )
        mock_urlopen.side_effect = err

        with self.assertRaises(RuntimeError) as ctx:
            fetch_user_token("observer", "bad")

        self.assertIn("HTTP 401", str(ctx.exception))

    @patch("ocafitsfiles._download.urlopen")
    def test_fetch_user_token_url_error(self, mock_urlopen):
        mock_urlopen.side_effect = URLError("network down")

        with self.assertRaises(RuntimeError) as ctx:
            fetch_user_token("observer", "secret")

        self.assertIn("network down", str(ctx.exception))

    @patch("ocafitsfiles._download.urlopen")
    def test_fetch_user_token_non_json_response(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse("not-json")

        with self.assertRaises(RuntimeError) as ctx:
            fetch_user_token("observer", "secret")

        self.assertIn("non-JSON response", str(ctx.exception))

    @patch("ocafitsfiles._download.urlopen")
    def test_fetch_user_token_missing_access_token(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse('{"token_type": "bearer"}')

        with self.assertRaises(RuntimeError) as ctx:
            fetch_user_token("observer", "secret")

        self.assertIn("missing access_token", str(ctx.exception))


class TestBackwardCompatImports(unittest.TestCase):
    """Ensure the package refactor didn't break existing imports."""

    def test_parse_filename_importable(self):
        from ocafitsfiles import parse_filename
        self.assertEqual(parse_filename("zb08c_1075_66218.fits"),
                         ("zb08c_1075_66218", None))

    def test_parse_metadata_importable(self):
        from ocafitsfiles import parse_metadata
        meta = parse_metadata("zb08c_1075_66218.fits")
        self.assertIsNotNone(meta)
        self.assertEqual(meta["telescope"], "zb08")

    def test_all_public_symbols_importable(self):
        import ocafitsfiles
        for name in ocafitsfiles.__all__:
            self.assertTrue(hasattr(ocafitsfiles, name), f"missing: {name}")


if __name__ == "__main__":
    unittest.main()

