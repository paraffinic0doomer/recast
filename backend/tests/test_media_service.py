import pytest

from app.services.media_service import MediaProcessingError, extract_audio, extract_metadata


def test_extract_metadata_reads_real_video_properties(sample_video):
    metadata = extract_metadata(sample_video)
    assert 1.5 < metadata.duration_seconds < 2.5
    assert metadata.width == 320
    assert metadata.height == 240
    assert 20 < metadata.fps < 30
    assert metadata.size_bytes > 0


def test_extract_metadata_missing_file(tmp_path):
    with pytest.raises(MediaProcessingError):
        extract_metadata(tmp_path / "does-not-exist.mp4")


def test_extract_audio_produces_16khz_mono_wav(sample_video, tmp_path, monkeypatch):
    import app.services.media_service as media_service

    monkeypatch.setattr(media_service, "AUDIO_DIR", tmp_path)
    audio_path = extract_audio(sample_video, "test-project")

    assert audio_path.exists()
    assert audio_path.suffix == ".wav"

    probed = extract_audio_sample_rate(audio_path)
    assert probed == 16000


def extract_audio_sample_rate(audio_path) -> int:
    import json
    import subprocess

    from app.core.config import settings

    result = subprocess.run(
        [
            settings.ffprobe_bin,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    probe = json.loads(result.stdout)
    return int(probe["streams"][0]["sample_rate"])
