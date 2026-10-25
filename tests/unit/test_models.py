from wikiskill.models import SessionTrajectory, TrajectoryStep


def test_trajectory_step_creation():
    step = TrajectoryStep(
        step_number=1,
        tool_name="bash",
        tool_input={"command": "ls"},
        observation="file.txt",
        is_error=False,
        latency_ms=10.0,
    )
    assert step.step_number == 1
    assert step.tool_name == "bash"
    assert not step.is_error


def test_session_trajectory_creation():
    traj = SessionTrajectory(
        session_id="s1",
        timestamp="2026-10-25T12:00:00Z",
        model_routed="test-model",
    )
    assert traj.session_id == "s1"
    assert traj.steps == []
    assert traj.final_status == "success"
