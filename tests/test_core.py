import tempfile
import unittest
from pathlib import Path

from media_ops.audit import AuditLog
from media_ops.database import connect, initialize_core
from media_ops.permissions import PermissionMatrix
from media_ops.venue import VenueRepository, VenueService


class CoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.connection = connect(Path(self.temp.name) / "app.sqlite3")
        initialize_core(self.connection)

    def tearDown(self):
        self.connection.close()
        self.temp.cleanup()

    def test_repository_version_and_audit(self):
        repository = VenueRepository(self.connection)
        repository.create_schema()
        service = VenueService(repository, PermissionMatrix(), AuditLog(self.connection))
        record = service.register("tenant", "record-1", {"name": "示例name", "timezone": "示例timezone", "capacity": 10, "address": "示例address"}, "operator-1", "operator")
        self.assertEqual(record.version, 1)
        viewed = service.view("tenant", "record-1", "viewer-1", "viewer")
        self.assertEqual(viewed["record_id"], "record-1")
        self.assertGreaterEqual(len(AuditLog(self.connection).history("tenant", "record-1")), 2)

    def test_all_schemas_initialize(self):
        from media_ops.cli import initialize
        initialize(self.connection)
        names = {row[0] for row in self.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("audit_log", names)
        self.assertIn("venues", names)
    def test_cancellation_happy_path(self):
            from media_ops.program import ProgramRepository
            from media_ops.reservation import ReservationRepository
            from media_ops.settlement import SettlementRepository
            from media_ops.culture_workflows import ProgramCancellationWorkflow
            programs = ProgramRepository(self.connection); programs.create_schema()
            reservations = ReservationRepository(self.connection); reservations.create_schema()
            settlements = SettlementRepository(self.connection); settlements.create_schema()
            program = programs.create("org", "p1", {"title":"夜游活动", "venue_id":"v1", "starts_at":"2026-10-01T19:00:00+08:00", "ends_at":"2026-10-01T21:00:00+08:00", "capacity":100}, "u", "PUBLISHED")
            reservations.create("org", "r1", {"program_id":"p1", "customer_ref":"c1", "quantity":2, "paid_amount":80, "currency":"CNY"}, "u", "CONFIRMED")
            result = ProgramCancellationWorkflow(self.connection).cancel("org", "p1", "u", "天气原因")
            self.assertEqual(result.cancelled_reservations, ("r1",))
            self.assertEqual(reservations.get("org", "r1").status, "CANCELLED")
            self.assertEqual(len(result.refund_settlements), 1)


if __name__ == "__main__":
    unittest.main()
