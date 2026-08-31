import pytest

from ..scripts.ccr_log_adapter import CCRLogAdapter
from ..scripts.wikiskill_dataclasses import SessionTrajectory, TrajectoryStep


@pytest.fixture
def mock_session_trajectory():
    return SessionTrajectory(
        session_id="test-session-123",
        timestamp="2026-08-31T10:00:00Z",
        model_routed="claude-3-opus",
        steps=[
            TrajectoryStep(
                1,
                "Bash",
                {"command": "ls -la"},
                """total 0
-rw-r--r--  1 user  group  0 Aug 31 10:00 file.txt""",
                False,
                150.5,
            ),
            TrajectoryStep(
                2, "Read", {"file_path": "file.txt"}, "1\tHello World!", False, 80.2
            ),
        ],
        final_status="success",
    )


# Test cases for CCRLogAdapter
def test_ccr_log_adapter_mock(mock_session_trajectory):
    adapter = CCRLogAdapter(ccr_log_source="mock")
    trajectory = adapter.get_latest_session_trajectory()
    adapter = CCRLogAdapter(ccr_log_source="mock")
    trajectory = adapter.get_latest_session_trajectory()
    assert trajectory == mock_session_trajectory
