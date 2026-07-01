import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


class EnumCoverageTest(unittest.TestCase):
    def test_inspection_item_status_matches_state_machine(self):
        from app.core.enums import InspectionItemStatus

        self.assertEqual(
            {status.value for status in InspectionItemStatus},
            {
                "pending",
                "checking",
                "candidate_waiting",
                "auto_completed",
                "manual_required",
                "confirmed",
                "inherited",
            },
        )

    def test_auto_check_status_matches_state_machine(self):
        from app.core.enums import AutoCheckStatus

        self.assertEqual(
            {status.value for status in AutoCheckStatus},
            {"success", "failed", "candidate_waiting", "manual_required", "error"},
        )

    def test_auto_check_result_is_separate_from_final_result(self):
        from app.core.enums import AutoCheckResult, InspectionResult

        self.assertEqual(
            {result.value for result in AutoCheckResult},
            {"pass", "fail", "not_found", "suspect", "manual_required", "error"},
        )
        self.assertEqual(
            {result.value for result in InspectionResult},
            {"pass", "fail", "conditional", "na", "inherit"},
        )


if __name__ == "__main__":
    unittest.main()
