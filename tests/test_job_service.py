from __future__ import annotations

from app.core.container import ServiceContainer


def test_job_service_skips_existing_outputs(container: ServiceContainer) -> None:
    first_report = container.job_service.run_batch(script_path="data/scripts/episode1.csv")
    second_report = container.job_service.run_batch(
        script_path="data/scripts/episode1.csv",
        skip_existing=True,
    )

    assert first_report.done == 3
    assert first_report.failed == 0
    assert second_report.skipped == 3
    assert (first_report.output_dir / "batch_report.json").exists()
    assert (first_report.output_dir / "failed_lines.json").exists()
