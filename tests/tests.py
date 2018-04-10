#!/usr/bin/env python

import unittest
import wstation
import os
import hashlib

_loc = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
_flpth = os.path.join(_loc, ) + '\\'

if __name__ == "__main__":

    class Tests(unittest.TestCase):

        def setUp(self):
            self.base = wstation.Base()
            print('\n{} (started)'.format(self._testMethodDoc))

        def tearDown(self):
            print('{} (ended)'.format(self._testMethodDoc))
            del self.base

        def test_basemethods_1(self):
            """Test integer or string to byte conversions"""
            self.assertEqual(self.base._byte(127), b'\x7f')
            self.assertEqual(self.base._byte(65).decode(), 'A')
            self.assertEqual(self.base._byte('A'), b'A')

        def test_basemethods_2(self):
            """Test byte or string to integer conversion"""
            self.assertEqual(self.base._ord(b'\x7f'), 127)
            self.assertEqual(self.base._ord('A'), 65)

        def test_basemethods_3(self):
            """Test signed int | binary string to integer conversion"""
            self.assertEqual(int('10000000', 2), 128)
            self.assertEqual(self.base._sign_int('10000000'), -128)
            self.assertEqual(self.base._sign_int('100'), -4)
            self.assertEqual(self.base._sign_int('011'), 3)

        def test_basemethods_4(self):
            """Test signed int | signed integer to binary string"""
            # limits # (-128 to 127 for 8 bits)
            self.assertEqual(self.base._signed_binstr(-128, 8), '10000000')
            with self.assertRaises(Exception):
                self.base._signed_binstr(-129, 8)

            self.assertEqual(self.base._signed_binstr(127, 8), '01111111')
            with self.assertRaises(Exception):
                self.base._signed_binstr(128, 8)

            # limits # (-16 to 15 for 5 bits)
            self.assertEqual(self.base._signed_binstr(-16, 5), '10000')
            with self.assertRaises(Exception):
                self.base._signed_binstr(-17, 5)

            self.assertEqual(self.base._signed_binstr(15, 5), '01111')
            with self.assertRaises(Exception):
                self.base._signed_binstr(16, 5)

            self.assertEqual(self.base._signed_binstr(-1, 8), '11111111')
            self.assertEqual(self.base._signed_binstr(127, 8), '01111111')

        def test_basemethods_5(self):
            """Test binascii"""
            self.assertEqual(self.base._b2h(b'\xff\xf7').decode(), 'fff7')
            self.assertEqual(self.base._h2b('fff7'), b'\xff\xf7')

        def test_basemethods_6(self):
            """Test nibbler and denibbler"""
            # 10100101 <> 00000101, 00001010
            self.assertEqual(self.base._denibble(b'\x05', b'\x0a'), b'\xa5')
            self.assertEqual(self.base._nibbler(b'\xa5'), (b'\x05', b'\x0a'))

        def test_parameters_limits(self):
            """test parameters (dictionary) size limits"""
            patch = wstation.Patch(['par0', 'par1'])
            lim = ('bB', {'b': [-128, 127], 'B': [0, 255]})
            par = wstation.Parameters(patch, {'par0': 0, 'par1': 0}, lim)
            patch.parameters = par

            par['par0'] = 127
            self.assertEqual(par['par0'], 127)
            with self.assertRaises(Exception):
                par['par0'] = 128

            par['par0'] = -128
            self.assertEqual(par['par0'], -128)
            with self.assertRaises(Exception):
                par['par0'] = -129

            par['par1'] = 255
            self.assertEqual(par['par1'], 255)
            with self.assertRaises(Exception):
                par['par1'] = 256

            par['par1'] = 0
            self.assertEqual(par['par1'], 0)
            with self.assertRaises(Exception):
                par['par1'] = -1

        @staticmethod
        def file_hash(fi):
            # return tuple (md5 hash hex, sha1 hash hex)
            with open(fi, 'rb') as f:
                data = f.read()
                md5 = hashlib.md5(data)
                sha1 = hashlib.sha1(data)
                return md5.hexdigest(), sha1.hexdigest()

        def hash_file_exports(self, imprt):
            # load 1 format, export 2 formats and return hashes from the exports
            file_expo0 = _flpth + "EXPORT.syx"
            file_expo1 = _flpth + "EXPORT.wsram"
            wsio = wstation.WSIO()
            bnk = wsio.load_bank(imprt)
            wsio.export_sysex(bnk, file_expo0)
            wsio.export_wsram(bnk, file_expo1)
            output = self.file_hash(file_expo0), self.file_hash(file_expo1)
            os.remove(file_expo0)
            os.remove(file_expo1)

            return output

        def test_xport_file(self):
            """
            Test Export files | compare hashes to verify integrity
            Used to compare file exports while changing Python versions
            the hashes variable was pregenerated in one version to be used as reference
            working in python 3.5.2 and 2.7.12
            """
            sysex_file1 = _flpth + "factory.syx"
            wsram_file1 = _flpth + "factory.wsram"
            sysex_file2 = _flpth + "aquila.syx"
            wsram_file2 = _flpth + "AQUILA.wsram"

            files = [sysex_file1, sysex_file2, wsram_file1, wsram_file2]

            # pregenerated hashes
            # for fl in files:
            #     print(self.file_hash(fl))

            hashes = [(('616863dff7eb304157875b890ebf45c5', '0f3edf9a8bdda5fe72cf8b39ba94c6219127ea00'),
                       ('ead428f519872e5c69a2d884c24f2ee0', 'a1bb2facce3c9ff4f183d143832f6c2cb0494244')),
                      (('c92e1fd1661196a166db48908ea82cc2', '460e069c40fef459b4a531f76e4da5bd41e3eab9'),
                       ('7c3ed3045089d9475437ad1e1e7490c0', 'a841566d73497bb59d5e3c08aa4fe0c5863c2adc')),
                      (('98838df5880d84a77fbe0dc652a036f0', '60c50711eaef32e621919f3b96453683b01fb606'),
                       ('ab7f2bad46e41813d5b863c04e4e6699', '28f2fb817289f3d60ab98b8ff6fda6aff44ba1dd')),
                      (('ea1301f2fda5117ff976f43b1c16e52f', '99395f820e388d12f782ef33c081538a8b4c200f'),
                       ('be3d0c87de5223c88e16982fc3676e9f', '96adfabef745c3fca195a6030b0d058e4811d6dd'))]

            for e, fl in enumerate(files):
                self.assertTupleEqual(hashes[e], self.hash_file_exports(fl))

    unittest.main()
