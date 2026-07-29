"""Tests for BenchmarkContext and PhaseRecord."""

import time

from scriptbench.context import BenchmarkContext, PhaseRecord

# ===================================================================
# PhaseRecord
# ===================================================================


class TestPhaseRecord:
    def test_create(self) -> None:
        """A PhaseRecord stores name and start time."""
        now = time.perf_counter()
        rec = PhaseRecord("compute", now)
        assert rec.name == "compute"
        assert rec.start == now
        assert rec.end is None

    def test_duration_before_end_returns_zero(self) -> None:
        """duration() returns 0.0 when end has not been set."""
        rec = PhaseRecord("setup", 100.0)
        assert rec.duration() == 0.0

    def test_duration_after_end_returns_delta(self) -> None:
        """duration() returns the difference once end is assigned."""
        rec = PhaseRecord("setup", 100.0)
        rec.end = 105.0
        assert rec.duration() == 5.0

    def test_duration_precision(self) -> None:
        """duration correctly handles sub-millisecond intervals."""
        rec = PhaseRecord("fast", 0.001_000)
        rec.end = 0.001_250
        assert rec.duration() == 0.00025


# ===================================================================
# BenchmarkContext
# ===================================================================


class TestBenchmarkContextInit:
    def test_stores_properties(self) -> None:
        """Constructor stores output_dir, temp_dir, and save_output."""
        ctx = BenchmarkContext(
            output_dir="/tmp/out", temp_dir="/tmp/t", save_output=True
        )
        assert ctx.output_dir == "/tmp/out"
        assert ctx.temp_dir == "/tmp/t"
        assert ctx.save_output is True

    def test_default_save_output(self) -> None:
        """save_output defaults to False."""
        ctx = BenchmarkContext(output_dir="/tmp/out", temp_dir="/tmp/t")
        assert ctx.save_output is False

    def test_initial_state(self) -> None:
        """No phases, no total timing before start/stop."""
        ctx = BenchmarkContext(output_dir="/tmp/out", temp_dir="/tmp/t")
        assert ctx.has_phases() is False
        assert ctx.total_time() == 0.0
        assert ctx.phase_times() == {}
        assert ctx.compute_time() is None
        assert ctx.save_time() is None


class TestBenchmarkContextPhases:
    def test_single_phase_is_recorded(self) -> None:
        """phase() creates a PhaseRecord and makes it current."""
        ctx = BenchmarkContext(output_dir="/tmp/o", temp_dir="/tmp/t")
        ctx._start()
        ctx.phase("setup")
        assert ctx.has_phases() is True
        assert "setup" in ctx.phase_times()

    def test_phase_switching_closes_previous(self) -> None:
        """Calling a second phase automatically closes the first."""
        ctx = BenchmarkContext(output_dir="/tmp/o", temp_dir="/tmp/t")
        ctx._start()
        ctx.phase("compute")
        # small delay
        time.sleep(0.005)
        ctx.phase("save")
        ctx._stop()  # close the last phase

        times = ctx.phase_times()
        assert "compute" in times
        assert "save" in times
        assert times["compute"] > 0.0
        assert times["save"] > 0.0

    def test_repeated_phase_names_accumulate(self) -> None:
        """Calling the same phase name twice adds their durations."""
        ctx = BenchmarkContext(output_dir="/tmp/o", temp_dir="/tmp/t")
        ctx._start()
        ctx.phase("read")
        time.sleep(0.003)
        ctx.phase("compute")
        time.sleep(0.004)
        ctx.phase("read")  # second 'read' block
        time.sleep(0.002)
        ctx._stop()

        times = ctx.phase_times()
        # There were two 'read' phases whose durations should be summed
        assert "read" in times
        assert times["read"] >= 0.005  # 0.003 + 0.002 (approx)

    def test_compute_time_returns_compute_phase(self) -> None:
        """compute_time() returns the value of the 'compute' phase."""
        ctx = BenchmarkContext(output_dir="/tmp/o", temp_dir="/tmp/t")
        ctx._start()
        ctx.phase("setup")
        ctx.phase("compute")
        time.sleep(0.005)
        ctx.phase("save")
        ctx._stop()

        ct = ctx.compute_time()
        assert ct is not None
        assert ct > 0.0
        # Should be the compute phase duration (approx)
        assert ctx.phase_times()["compute"] == ct

    def test_compute_time_none_when_no_compute(self) -> None:
        """compute_time() returns None when no 'compute' phase was recorded."""
        ctx = BenchmarkContext(output_dir="/tmp/o", temp_dir="/tmp/t")
        ctx._start()
        ctx.phase("setup")
        ctx._stop()
        assert ctx.compute_time() is None

    def test_save_time_returns_save_phase(self) -> None:
        """save_time() returns the value of the 'save' phase."""
        ctx = BenchmarkContext(output_dir="/tmp/o", temp_dir="/tmp/t")
        ctx._start()
        ctx.phase("compute")
        ctx.phase("save")
        time.sleep(0.003)
        ctx._stop()

        st = ctx.save_time()
        assert st is not None
        assert st >= 0.003
        assert ctx.phase_times()["save"] == st

    def test_save_time_none_when_no_save(self) -> None:
        """save_time() returns None when no 'save' phase was recorded."""
        ctx = BenchmarkContext(output_dir="/tmp/o", temp_dir="/tmp/t")
        ctx._start()
        ctx.phase("compute")
        ctx._stop()
        assert ctx.save_time() is None


class TestBenchmarkContextTotalTiming:
    def test_total_time_after_full_run(self) -> None:
        """total_time() returns wall-clock time between _start and _stop."""
        ctx = BenchmarkContext(output_dir="/tmp/o", temp_dir="/tmp/t")
        ctx._start()
        time.sleep(0.01)
        ctx._stop()

        tt = ctx.total_time()
        assert tt >= 0.01
        assert isinstance(tt, float)

    def test_total_time_zero_before_start(self) -> None:
        """total_time() is 0.0 before _start is called."""
        ctx = BenchmarkContext(output_dir="/tmp/o", temp_dir="/tmp/t")
        assert ctx.total_time() == 0.0


class TestBenchmarkContextStopClosesCurrentPhase:
    def test_stop_closes_current_phase(self) -> None:
        """_stop() assigns an end time to any open phase."""
        ctx = BenchmarkContext(output_dir="/tmp/o", temp_dir="/tmp/t")
        ctx._start()
        ctx.phase("open_phase")
        time.sleep(0.003)
        ctx._stop()

        times = ctx.phase_times()
        assert "open_phase" in times
        assert times["open_phase"] >= 0.003


class TestBenchmarkContextHasPhases:
    def test_false_when_no_phases(self) -> None:
        ctx = BenchmarkContext(output_dir="/tmp/o", temp_dir="/tmp/t")
        assert ctx.has_phases() is False

    def test_true_after_phase_called(self) -> None:
        ctx = BenchmarkContext(output_dir="/tmp/o", temp_dir="/tmp/t")
        ctx.phase("work")
        assert ctx.has_phases() is True


class TestBenchmarkContextIntegration:
    """End-to-end checks of a realistic usage pattern."""

    def test_full_lifecycle(self) -> None:
        """Simulate a complete benchmark run and verify all timing."""
        ctx = BenchmarkContext(
            output_dir="/tmp/out", temp_dir="/tmp/temp", save_output=True
        )

        ctx._start()
        ctx.phase("setup")
        time.sleep(0.002)

        ctx.phase("compute")
        total = sum(i * i for i in range(10_000))
        time.sleep(0.005)

        ctx.phase("save")
        time.sleep(0.002)
        ctx._stop()

        tt = ctx.total_time()
        pt = ctx.phase_times()

        assert total > 0  # sanity: Python did work
        assert tt >= 0.009  # ~9 ms of sleep
        assert "setup" in pt
        assert "compute" in pt
        assert "save" in pt
        assert pt["setup"] > 0.0
        assert pt["compute"] > 0.0
        assert pt["save"] > 0.0
        assert ctx.has_phases() is True
        assert ctx.compute_time() == pt["compute"]
        assert ctx.save_time() == pt["save"]

    def test_phase_times_returns_copy(self) -> None:
        """phase_times() returns all phases regardless of ordering."""
        ctx = BenchmarkContext(output_dir="/tmp/o", temp_dir="/tmp/t")
        ctx._start()
        ctx.phase("a")
        ctx.phase("b")
        ctx.phase("c")
        ctx._stop()
        pt = ctx.phase_times()
        assert set(pt.keys()) == {"a", "b", "c"}
        assert all(v >= 0 for v in pt.values())
