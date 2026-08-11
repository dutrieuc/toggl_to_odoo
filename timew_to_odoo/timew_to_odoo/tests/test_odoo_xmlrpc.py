import unittest
from unittest import mock
import timew_to_odoo.timew_to_odoo.odoo_xmlrpc as xmlrpc_module

from timew_to_odoo.timew_to_odoo.odoo_xmlrpc import OdooXmlRpc


def make_rpc():
    common = mock.Mock()
    obj = mock.Mock()
    with mock.patch.object(
        xmlrpc_module, "XmlRpcServerProxy", side_effect=[common, obj]
    ):
        rpc = OdooXmlRpc(
            url="https://odoo.example.com",
            db="testdb",
            username="admin",
            password="secret",
        )
    return rpc, common, obj


class OdooXmlRpcTestCase(unittest.TestCase):
    def setUp(self):
        self.rpc, self.common, self.obj = make_rpc()

    def assert_not_authed(self):
        self.assertFalse(self.rpc.is_logged_in)
        with self.assertRaises(SystemError):
            self.rpc.search_read("res.partner", [("id", ">", 0)])

    def test_authenticate_success(self):
        self.common.authenticate.return_value = 42
        self.assertEqual(self.rpc.authenticate(), 42)
        self.assertTrue(self.rpc.is_logged_in)
        self.assertEqual(self.rpc.uid, 42)

    def test_authenticate_failure(self):
        self.common.authenticate.return_value = "not-an-int"
        with self.assertRaises(ValueError):
            self.rpc.authenticate()

    def test_commands_require_authentication(self):
        self.assert_not_authed()

    def test_search_read_delegates(self):
        self.rpc.uid = 1
        self.obj.execute_kw.return_value = [{"id": 1, "name": "x"}]
        results = self.rpc.search_read(
            "res.partner", [("id", ">", 0)], fields=["name"], limit=10
        )
        self.assertEqual(results, [{"id": 1, "name": "x"}])
        self.obj.execute_kw.assert_called_once_with(
            "testdb", 1, "secret", "res.partner", "search_read",
            ([("id", ">", 0)],), {"fields": ["name"], "limit": 10},
        )

    def test_read_delegates(self):
        self.rpc.uid = 1
        self.obj.execute_kw.return_value = [{"id": 1, "name": "x"}]
        self.assertEqual(self.rpc.read("res.partner", 1, ["name"]), [{"id": 1, "name": "x"}])
        self.obj.execute_kw.assert_called_once_with(
            "testdb", 1, "secret", "res.partner", "read", (1,), {"fields": ["name"]}
        )

    def test_name_search_validates_results(self):
        self.rpc.uid = 1
        self.obj.execute_kw.return_value = [(1, "x")]
        self.assertEqual(self.rpc.name_search("res.partner", "x"), [(1, "x")])

    def test_name_search_rejects_malformed_result(self):
        self.rpc.uid = 1
        self.obj.execute_kw.return_value = ["bad"]
        with self.assertRaises(AssertionError):
            self.rpc.name_search("res.partner", "x")

    def test_name_get(self):
        self.rpc.uid = 1
        self.obj.execute_kw.return_value = [(1, "x")]
        self.assertEqual(self.rpc.name_get("res.partner", [1]), [(1, "x")])

    def test_create_returns_int(self):
        self.rpc.uid = 1
        self.obj.execute_kw.return_value = 7
        self.assertEqual(self.rpc.create("res.partner", {"name": "x"}), 7)

    def test_unlink_delegates(self):
        self.rpc.uid = 1
        self.obj.execute_kw.return_value = True
        self.assertTrue(self.rpc.unlink("res.partner", [1]))
        self.assertTrue(self.rpc.delete("res.partner", [1]))