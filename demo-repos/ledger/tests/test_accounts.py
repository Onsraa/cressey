import unittest

from ledger.accounts import emails, invoice_total
from ledger.db import connect


class AccountsTest(unittest.TestCase):
    def setUp(self):
        self.conn = connect()

    def test_emails_are_lowercase(self):
        self.assertTrue(all(e == e.lower() for e in emails(self.conn)))

    def test_invoice_total_is_rounded(self):
        self.assertEqual(invoice_total(self.conn, 1), 200.5)
