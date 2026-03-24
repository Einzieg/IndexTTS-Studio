from __future__ import annotations

from app.core.container import ServiceContainer


def test_speaker_service_loads_profiles(container: ServiceContainer) -> None:
    speakers = container.speaker_service.load_speakers()

    assert sorted(speakers) == ["主角A", "反派B", "旁白"]
    assert speakers["主角A"].ref_audio.exists()
    assert speakers["主角A"].options.emo_audio is not None


def test_speaker_service_lists_serializable_profiles(container: ServiceContainer) -> None:
    profiles = container.speaker_service.list_speaker_profiles()

    assert [profile["name"] for profile in profiles] == ["主角A", "反派B", "旁白"]
    hero_profile = next(profile for profile in profiles if profile["name"] == "主角A")
    assert hero_profile["ref_audio"].replace("\\", "/").endswith("data/refs/hero_a.wav")
    assert hero_profile["options"]["temperature"] == 0.8
