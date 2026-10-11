import unittest

from ledger.db import connect, count


class FreshInstallTest(unittest.TestCase):
    def test_fresh_install_has_no_users(self):
        # A fresh install starts with no customer accounts.
        self.assertEqual(count(connect(), "users"), 0)
