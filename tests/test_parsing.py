import unittest
from ocafitsfiles import parse_filename, parse_metadata

class TestOcaFitsFiles(unittest.TestCase):
    def test_parse_filename(self):
        self.assertEqual(parse_filename('zb08c_1075_66218.fits'), ('zb08c_1075_66218', None))
        self.assertEqual(parse_filename('zb08c_1075_66218_zdf.fits'), ('zb08c_1075_66218', 'zdf'))
        self.assertEqual(parse_filename('/any/path/zb08c_1075_49661_master_f_V.fits'), ('zb08c_1075_49661', 'master_f_V'))

    def test_parse_metadata(self):
        meta = parse_metadata('zb08c_1075_66218.fits')
        self.assertIsNotNone(meta)
        self.assertEqual(meta['telescope'], 'zb08')
        self.assertEqual(meta['instr'], 'c')
        self.assertEqual(meta['night'], '1075')
        self.assertEqual(meta['count'], '66218')
        self.assertIsNone(meta['suffix'])

if __name__ == '__main__':
    unittest.main()

