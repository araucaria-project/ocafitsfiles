"""Regression test for iter_calib_files crashing on unparseable filenames.

When a processed directory contains a .fits file whose name does not match
the OCA naming convention, parse_filename returns (None, None).  The code
must skip such files gracefully instead of passing None into canonical_path.

See: TypeError: 'NoneType' object is not subscriptable
     in canonical_path() when basename is None.
"""

import tempfile
import unittest
from pathlib import Path

from ocafitsfiles import iter_calib_files


class TestIterCalibUnparseableFile(unittest.TestCase):
    """iter_calib_files must not crash on non-OCA filenames in processed dirs."""

    def _make_tree(self, tmp: Path) -> Path:
        """Build a minimal processed-ofp tree with one foreign file."""
        root = tmp
        # zdf directory for jk15c_1091_58100
        sci_dir = root / "jk15" / "processed-ofp" / "science" / "1091" / "jk15c_1091_58100"
        sci_dir.mkdir(parents=True)

        # Normal self-reference (zdf file itself)
        (sci_dir / "jk15c_1091_58100_zdf.fits").touch()

        # A file that does NOT match OCA naming (e.g. a log or foreign artifact)
        (sci_dir / "some_random_file.fits").touch()

        # A valid calibration symlink (master zero)
        (sci_dir / "jk15c_1091_52446_master_z.fits").touch()

        return root

    def test_unparseable_file_skipped(self):
        """Foreign .fits files must be silently skipped, not cause TypeError."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_tree(Path(tmp))
            # This must not raise TypeError
            results = iter_calib_files(
                "jk15c_1091_58100", "zdf", root,
                master_zero=True, master_dark=False, master_flat=False,
                raw_zero=False, raw_dark=False, raw_flat=False,
            )
            # The master_z file should be found
            basenames = [r[3] for r in results]
            self.assertIn("jk15c_1091_52446", basenames)
            # The foreign file must NOT appear in results
            for _, _, _, fb, _ in results:
                self.assertIsNotNone(fb)


class TestIterCalibRawSuffixNone(unittest.TestCase):
    """Raw files (suffix=None) must never inherit the ZDF's calibration set."""

    def _make_tree(self, tmp: Path) -> Path:
        """Build a processed-ofp science dir populated as if ZDF already ran."""
        root = tmp
        sci_dir = root / "jk15" / "processed-ofp" / "science" / "1091" / "jk15c_1091_58100"
        sci_dir.mkdir(parents=True)
        (sci_dir / "jk15c_1091_58100_zdf.fits").touch()
        (sci_dir / "jk15c_1091_52446_master_z.fits").touch()
        return root

    def test_raw_suffix_returns_no_calib_files(self):
        """A raw-only observation must get an empty result, not the ZDF's masters."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_tree(Path(tmp))
            results = iter_calib_files(
                "jk15c_1091_58100", None, root,
                master_zero=True, master_dark=True, master_flat=True,
                raw_zero=True, raw_dark=True, raw_flat=True,
            )
            self.assertEqual(results, [])


class TestIterCalibNoneBasenameRegression(unittest.TestCase):
    """Directly verify that parse_filename returning None doesn't propagate."""

    def test_parse_filename_returns_none_for_foreign(self):
        from ocafitsfiles import parse_filename
        fb, fs = parse_filename("some_random_file.fits")
        self.assertIsNone(fb)
        self.assertIsNone(fs)


if __name__ == "__main__":
    unittest.main()
