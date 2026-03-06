import unittest
from ocafitsfiles import render_download_script, TEMPLATE_VERSION, DEFAULT_API_ENDPOINT


class TestRenderDownloadScript(unittest.TestCase):

    def _render(self, **kwargs):
        defaults = dict(
            data_block="file1.fits  extra\nfile2.fits  extra2",
            api_endpoint="https://api.ocadb.space/api/v1/observations",
            api_token="tok_secret123",
            expires_in=3600,
            dl_timeout=60,
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
        self.assertGreaterEqual(TEMPLATE_VERSION, 3)

    def test_endpoint_substituted(self):
        script = self._render(api_endpoint="https://api.ocadb.space/api/v1/observations")
        self.assertIn('API_ENDPOINT="https://api.ocadb.space/api/v1/observations"', script)

    def test_endpoint_trailing_slash_stripped(self):
        script = self._render(api_endpoint="https://api.ocadb.space/api/v1/observations/")
        self.assertIn('API_ENDPOINT="https://api.ocadb.space/api/v1/observations"', script)

    def test_token_substituted(self):
        script = self._render(api_token="abc_xyz")
        self.assertIn('API_TOKEN="abc_xyz"', script)

    def test_expires_in_substituted(self):
        script = self._render(expires_in=15000000)
        self.assertIn('EXPIRES_IN="15000000"', script)

    def test_dl_timeout_substituted(self):
        script = self._render(dl_timeout=42)
        self.assertIn('DL_TIMEOUT="42"', script)

    def test_data_block_embedded(self):
        script = self._render(data_block="alpha.fits\nbeta.fits\n")
        # Data block is inside a heredoc in data_lines()
        self.assertIn("alpha.fits\n", script)
        self.assertIn("beta.fits\n", script)
        # Heredoc delimiters present
        self.assertIn("cat <<'__DATA__'", script)
        self.assertIn("\n__DATA__\n", script)

    def test_no_raw_placeholders_remain(self):
        """Ensure no $word placeholders are left unsubstituted."""
        script = self._render()
        for placeholder in ("$api_endpoint", "$api_token", "$expires_in", "$dl_timeout", "$data_block"):
            self.assertNotIn(placeholder, script)

    def test_trailing_newline(self):
        script = self._render()
        self.assertTrue(script.endswith("\n"))

    def test_empty_data_block(self):
        script = self._render(data_block="")
        self.assertIn("cat <<'__DATA__'", script)
        self.assertIn("\n__DATA__\n", script)

    def test_quotes_in_token_escaped(self):
        script = self._render(api_token='tok"with"quotes')
        self.assertIn(r'tok\"with\"quotes', script)

    def test_fetch_url_pattern(self):
        """Generated script builds /by-filename/{key}/plainurl?expires_in= URLs."""
        script = self._render()
        self.assertIn("/by-filename/", script)
        self.assertIn("/plainurl?expires_in=", script)

    def test_default_endpoint(self):
        self.assertEqual(DEFAULT_API_ENDPOINT, "https://api.ocadb.space/api/v1/observations")

    def test_curl_auth_header(self):
        """curl call includes Bearer auth and Content-Type."""
        script = self._render()
        self.assertIn('Authorization: Bearer', script)
        self.assertIn('Content-Type: application/json', script)


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

