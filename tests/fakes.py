"""Shared in-memory fakes used by the test-suite.

These fakes stand in for the external services (Toggl's API and an Odoo
XML-RPC database) so that the upload code can be exercised end-to-end
without any network access.
"""


class FakeShelf(dict):
    """A minimal ``shelve``-like dict supporting the history ``sync()``."""

    def sync(self):
        """No-op: data is already persisted (it lives in memory)."""


class FakeOdooXmlRpc:
    """
    In-memory implementation of the subset of the Odoo XML-RPC object API
    that :mod:`toggl_to_odoo.odoo_upload` relies on.

    Records are stored per model in ``self.records`` (``model -> id -> record``),
    so tests can both seed the "database" and assert on what got written.
    """

    def __init__(self, url=None, db=None, username=None, password=None):
        self.uid = None
        self.url = url
        self.db_name = db
        self.username = username
        self.password = password
        self.records = {}
        self._next_id = {}

    # -- helpers used to pre-populate the "database" ----------------------

    def _model_records(self, model):
        if model not in self.records:
            self.records[model] = {}
        return self.records[model]

    def _alloc_id(self, model):
        """Return the next sequential id for ``model`` without reusing any."""
        next_id = self._next_id.get(model, 1)
        self._next_id[model] = next_id + 1
        return next_id

    def add(self, model, record):
        """
        Insert a record, honouring the given id. This bypasses ``create()``
        so tests can seed the database before running the upload.
        """
        recs = self._model_records(model)
        rid = record.get("id")
        if rid is None:
            rid = self._alloc_id(model)
        elif rid >= self._next_id.get(model, 1):
            self._next_id[model] = rid + 1
        if rid in recs:
            raise AssertionError(f"Odoo id {rid} already exists in model {model}")
        recs[rid] = dict(record, id=rid)
        return rid

    def get(self, model, rid):
        """Return the raw stored record for ``rid``, or ``None``."""
        return self._model_records(model).get(rid)

    # -- xmlrpc commands --------------------------------------------------

    def authenticate(self):
        if self.uid is None:
            self.uid = 1
        return self.uid

    def name_search(self, model, name, limit=None, operator=None):
        records = self._model_records(model)
        matches = [record for record in records.values() if name in record.get("name", "")]
        if limit is not None:
            matches = matches[:limit]
        return [(record["id"], record["name"]) for record in matches]

    def read(self, model, ids, fields=None):
        records = self._model_records(model)
        if isinstance(ids, int):
            ids = [ids]
        results = []
        for rid in ids:
            record = records.get(rid)
            if record is None:
                continue
            if fields is not None:
                record = {f: record[f] for f in fields if f in record}
                record["id"] = rid
            results.append(record)
        return results

    def create(self, model, values):
        rid = self._alloc_id(model)
        self._model_records(model)[rid] = dict(values, id=rid)
        return rid

    def unlink(self, model, ids):
        records = self._model_records(model)
        if isinstance(ids, int):
            ids = [ids]
        for rid in list(ids):
            records.pop(rid, None)
        return True