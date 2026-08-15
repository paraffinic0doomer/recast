from types import SimpleNamespace

import pytest

from app.services.transcription_service import (
    LocalWhisperTranscriptionService,
    OpenAIWhisperTranscriptionService,
    TranscriptionError,
    TranscriptionNotConfiguredError,
    get_transcription_service,
)


def test_auto_prefers_groq_when_key_present(monkeypatch):
    """Hosted Groq is ~13x faster than CPU Whisper on longer videos."""
    import app.services.transcription_service as ts

    monkeypatch.setattr(ts.settings, "transcription_backend", "auto")
    monkeypatch.setattr(ts.settings, "groq_api_key", "gsk-test")
    monkeypatch.setattr(ts, "local_whisper_available", lambda: True)

    service = get_transcription_service()
    assert isinstance(service, OpenAIWhisperTranscriptionService)
    assert service._provider == "Groq"
    assert "groq.com" in str(service._client.base_url)


def test_auto_prefers_local_when_no_groq_key(monkeypatch):
    import app.services.transcription_service as ts

    monkeypatch.setattr(ts.settings, "transcription_backend", "auto")
    monkeypatch.setattr(ts.settings, "groq_api_key", "")
    monkeypatch.setattr(ts, "local_whisper_available", lambda: True)
    monkeypatch.setattr(ts.settings, "openai_api_key", "sk-real-looking-key")

    assert isinstance(get_transcription_service(), LocalWhisperTranscriptionService)


def test_auto_falls_back_to_openai_when_local_missing(monkeypatch):
    import app.services.transcription_service as ts

    monkeypatch.setattr(ts.settings, "transcription_backend", "auto")
    monkeypatch.setattr(ts.settings, "groq_api_key", "")
    monkeypatch.setattr(ts, "local_whisper_available", lambda: False)
    monkeypatch.setattr(ts.settings, "openai_api_key", "sk-real-looking-key")

    assert isinstance(get_transcription_service(), OpenAIWhisperTranscriptionService)


def test_auto_raises_when_no_backend_available(monkeypatch):
    import app.services.transcription_service as ts

    monkeypatch.setattr(ts.settings, "transcription_backend", "auto")
    monkeypatch.setattr(ts.settings, "groq_api_key", "")
    monkeypatch.setattr(ts, "local_whisper_available", lambda: False)
    monkeypatch.setattr(ts.settings, "openai_api_key", "sk-your-key-here")

    with pytest.raises(TranscriptionNotConfiguredError, match="GROQ_API_KEY"):
        get_transcription_service()


def test_explicit_groq_requires_key(monkeypatch):
    import app.services.transcription_service as ts

    monkeypatch.setattr(ts.settings, "transcription_backend", "groq")
    monkeypatch.setattr(ts.settings, "groq_api_key", "")

    with pytest.raises(TranscriptionNotConfiguredError, match="GROQ_API_KEY"):
        get_transcription_service()


def test_explicit_openai_backend_requires_key(monkeypatch):
    import app.services.transcription_service as ts

    monkeypatch.setattr(ts.settings, "transcription_backend", "openai")
    monkeypatch.setattr(ts.settings, "openai_api_key", "sk-your-key-here")

    with pytest.raises(TranscriptionNotConfiguredError, match="OPENAI_API_KEY"):
        get_transcription_service()


def test_explicit_local_backend_requires_package(monkeypatch):
    import app.services.transcription_service as ts

    monkeypatch.setattr(ts.settings, "transcription_backend", "local")
    monkeypatch.setattr(ts.settings, "groq_api_key", "")
    monkeypatch.setattr(ts, "local_whisper_available", lambda: False)

    with pytest.raises(TranscriptionNotConfiguredError, match="pip install faster-whisper"):
        get_transcription_service()


def test_unknown_backend_rejected(monkeypatch):
    import app.services.transcription_service as ts

    monkeypatch.setattr(ts.settings, "transcription_backend", "banana")
    with pytest.raises(TranscriptionNotConfiguredError, match="Unknown TRANSCRIPTION_BACKEND"):
        get_transcription_service()


def test_whisper_service_parses_verbose_json_response(tmp_path, monkeypatch):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFFfake")

    service = OpenAIWhisperTranscriptionService(api_key="sk-test", model="whisper-1")

    fake_response = SimpleNamespace(
        text="  Hello there, welcome back.  ",
        language="english",
        duration=12.5,
        segments=[
            SimpleNamespace(start=0.0, end=4.2, text=" Hello there, "),
            SimpleNamespace(start=4.2, end=12.5, text=" welcome back. "),
        ],
    )
    monkeypatch.setattr(
        service._client.audio.transcriptions,
        "create",
        lambda **kwargs: fake_response,
    )

    result = service.transcribe(audio)

    assert result.text == "Hello there, welcome back."
    # Groq returns "English" where local Whisper returns "en" — normalised here.
    assert result.language == "en"
    assert result.duration == 12.5
    assert len(result.segments) == 2
    assert result.segments[0].text == "Hello there,"
    assert result.segments[1].start == 4.2

    payload = result.to_dict()
    assert payload["segments"][1]["end"] == 12.5


def test_whisper_service_missing_audio_file(tmp_path):
    service = OpenAIWhisperTranscriptionService(api_key="sk-test", model="whisper-1")
    with pytest.raises(TranscriptionError, match="Audio file not found"):
        service.transcribe(tmp_path / "nope.wav")


def test_whisper_service_wraps_api_errors(tmp_path, monkeypatch):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFFfake")

    service = OpenAIWhisperTranscriptionService(api_key="sk-test", model="whisper-1")

    def boom(**kwargs):
        raise RuntimeError("upstream exploded")

    monkeypatch.setattr(service._client.audio.transcriptions, "create", boom)

    with pytest.raises(TranscriptionError, match="upstream exploded"):
        service.transcribe(audio)


def test_local_whisper_missing_audio_file(tmp_path):
    service = LocalWhisperTranscriptionService("base", "int8")
    with pytest.raises(TranscriptionError, match="Audio file not found"):
        service.transcribe(tmp_path / "nope.wav")


# --- language normalisation --------------------------------------------------


def test_normalize_language_maps_provider_variants():
    from app.services.transcription_service import normalize_language

    assert normalize_language("English") == "en"
    assert normalize_language("english") == "en"
    assert normalize_language("en") == "en"
    assert normalize_language("Bengali") == "bn"
    assert normalize_language(None) is None
    assert normalize_language("  ") is None
    # Unknown languages pass through lowercased rather than being dropped.
    assert normalize_language("Klingon") == "klingon"


# --- upload size handling ----------------------------------------------------


def test_oversized_audio_rejected_with_actionable_message(tmp_path, monkeypatch):
    """Hosted APIs cap uploads; the error must point at the local fallback."""
    import app.services.transcription_service as ts

    audio = tmp_path / "big.wav"
    audio.write_bytes(b"x" * 100)

    service = ts.OpenAIWhisperTranscriptionService(
        api_key="gsk-test", model="whisper-large-v3-turbo",
        base_url=ts.GROQ_BASE_URL, max_upload_bytes=50, provider="Groq",
    )
    # Skip real ffmpeg: pretend compression is unavailable so the raw file is used.
    monkeypatch.setattr(
        ts, "compress_audio_for_upload",
        lambda p: (_ for _ in ()).throw(ts.MediaProcessingError("no ffmpeg")),
    )

    with pytest.raises(TranscriptionError, match="TRANSCRIPTION_BACKEND=local"):
        service.transcribe(audio)


def test_compressed_upload_is_cleaned_up(tmp_path, monkeypatch):
    """The temporary FLAC must not accumulate in storage."""
    import app.services.transcription_service as ts
    from types import SimpleNamespace

    audio = tmp_path / "a.wav"
    audio.write_bytes(b"x" * 10)
    flac = tmp_path / "a.flac"
    flac.write_bytes(b"y" * 5)

    monkeypatch.setattr(ts, "compress_audio_for_upload", lambda p: flac)

    service = ts.OpenAIWhisperTranscriptionService(
        api_key="gsk-test", model="m", base_url=ts.GROQ_BASE_URL, provider="Groq"
    )
    monkeypatch.setattr(
        service._client.audio.transcriptions, "create",
        lambda **kw: SimpleNamespace(text="hi", language="English", duration=1.0, segments=[]),
    )

    result = service.transcribe(audio)
    assert result.text == "hi"
    assert result.language == "en"
    assert not flac.exists(), "temporary FLAC should be deleted"
    assert audio.exists(), "original WAV must be preserved"
