import datetime
import unittest

from ocafitsfiles import night_set, ensure_oca_julian


class TestNightSet(unittest.TestCase):
    """Tests for the night_set() convenience builder."""

    def test_none_returns_none(self):
        self.assertIsNone(night_set(None))

    def test_empty_list_returns_none(self):
        self.assertIsNone(night_set([]))

    def test_single_int(self):
        result = night_set([1075])
        self.assertEqual(result, {1075})

    def test_single_string_int(self):
        result = night_set(["1075"])
        self.assertEqual(result, {1075})

    def test_iso_date(self):
        expected = ensure_oca_julian("2026-03-15")
        result = night_set(["2026-03-15"])
        self.assertEqual(result, {expected})

    def test_mixed_types(self):
        iso_night = ensure_oca_julian("2026-03-15")
        result = night_set([1075, "1080", "2026-03-15"])
        self.assertEqual(result, {1075, 1080, iso_night})

    def test_returns_set_type(self):
        result = night_set([1075])
        self.assertIsInstance(result, set)

    def test_duplicates_collapsed(self):
        result = night_set([1075, 1075, "1075"])
        self.assertEqual(result, {1075})
        self.assertEqual(len(result), 1)

    def test_invalid_value_raises(self):
        with self.assertRaises(ValueError):
            night_set(["not-a-date-or-int"])

    def test_iso_datetime_string(self):
        expected = ensure_oca_julian("2026-03-15T22:30:00")
        result = night_set(["2026-03-15T22:30:00"])
        self.assertEqual(result, {expected})


class TestNightSetExportedFromPackage(unittest.TestCase):
    """Verify night_set is properly exported."""

    def test_importable_from_package(self):
        import ocafitsfiles
        self.assertTrue(hasattr(ocafitsfiles, "night_set"))
        self.assertIn("night_set", ocafitsfiles.__all__)


if __name__ == "__main__":
    unittest.main()
