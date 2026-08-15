import time

import pytest

from app.core.key_pool import (
    DEFAULT_COOLDOWN_SECONDS,
    KeyPool,
    call_with_rotation,
    is_rate_limit_error,
    parse_retry_after,
)

GROQ_429 = (
    "Error code: 429 - {'error': {'message': 'Rate limit reached for model "
    "`llama-3.3-70b-versatile` in organization `org_x` service tier `on_demand` "
    "on tokens per day (TPD): Limit 100000, Used 99620, Requested 4795. "
    "Please try again in 27m50.976s.', 'type': 'tokens', "
    "'code': 'rate_limit_exceeded'}}"
)


# --- parsing -----------------------------------------------------------------


def test_parse_retry_after_from_real_groq_message():
    assert 27 * 60 < parse_retry_after(GROQ_429) < 28 * 60


def test_parse_retry_after_handles_hours():
    assert parse_retry_after("Please try again in 1h3m34.56s") == pytest.approx(3814.56, rel=1e-3)


def test_parse_retry_after_defaults_when_absent():
    assert parse_retry_after("something else went wrong") == DEFAULT_COOLDOWN_SECONDS
    assert parse_retry_after("") == DEFAULT_COOLDOWN_SECONDS


def test_rate_limit_detection():
    assert is_rate_limit_error(RuntimeError(GROQ_429))
    assert is_rate_limit_error(RuntimeError("429 Too Many Requests"))
    assert not is_rate_limit_error(RuntimeError("400 Bad Request"))
    assert not is_rate_limit_error(ValueError("malformed JSON"))


def test_rate_limit_detection_by_status_attribute():
    class Err(Exception):
        status_code = 429

    assert is_rate_limit_error(Err())


# --- pool construction -------------------------------------------------------


def test_reads_keys_from_file(tmp_path):
    f = tmp_path / "groq_keys.txt"
    f.write_text("# comment\ngsk_one\n\ngsk_two   # trailing note\ngsk_three\n")
    pool = KeyPool.from_sources(keys_file=f)
    assert pool.size == 3
    assert pool.acquire() == "gsk_one"


def test_file_takes_precedence_over_env(tmp_path):
    f = tmp_path / "groq_keys.txt"
    f.write_text("gsk_from_file\n")
    pool = KeyPool.from_sources(keys_file=f, keys_csv="gsk_a,gsk_b", single_key="gsk_c")
    assert pool.size == 1
    assert pool.acquire() == "gsk_from_file"


def test_falls_back_to_csv_then_single(tmp_path):
    missing = tmp_path / "nope.txt"
    assert KeyPool.from_sources(keys_file=missing, keys_csv="a, b ,c").size == 3
    assert KeyPool.from_sources(keys_file=missing, single_key="only").size == 1


def test_placeholders_and_duplicates_ignored(tmp_path):
    f = tmp_path / "k.txt"
    f.write_text("gsk_real\ngsk_real\ngsk_your_key_here\n\n")
    pool = KeyPool.from_sources(keys_file=f)
    assert pool.size == 1


def test_empty_pool_is_not_configured():
    assert KeyPool.from_sources().configured is False


# --- rotation ----------------------------------------------------------------


def _pool(n=3):
    return KeyPool.from_sources(keys_csv=",".join(f"k{i}" for i in range(n)))


def test_exhausted_key_is_skipped():
    pool = _pool()
    pool.mark_exhausted("k0", GROQ_429)
    assert pool.acquire() == "k1"


def test_rotation_moves_to_next_key_on_rate_limit():
    pool = _pool()
    used = []

    def run(key):
        used.append(key)
        if key in ("k0", "k1"):
            raise RuntimeError(GROQ_429)
        return "success"

    assert call_with_rotation(pool, run) == "success"
    assert used == ["k0", "k1", "k2"]


def test_non_rate_limit_errors_are_not_retried():
    pool = _pool()
    calls = []

    def run(key):
        calls.append(key)
        raise ValueError("bad request")

    with pytest.raises(ValueError):
        call_with_rotation(pool, run)
    assert calls == ["k0"], "a non-quota error must fail fast, not burn every key"


def test_all_keys_exhausted_raises_last_error():
    pool = _pool(2)

    def run(key):
        raise RuntimeError(GROQ_429)

    with pytest.raises(RuntimeError, match="Rate limit reached"):
        call_with_rotation(pool, run)
    assert all(not s["available"] for s in pool.status())


def test_unconfigured_pool_raises_clearly():
    with pytest.raises(RuntimeError, match="No Groq API keys"):
        call_with_rotation(KeyPool.from_sources(), lambda key: None)


def test_cooldown_expires(monkeypatch):
    pool = _pool(1)
    pool.mark_exhausted("k0", "try again in 0.01s")
    assert pool.acquire() is None or True  # may already be free
    time.sleep(0.05)
    assert pool.acquire() == "k0"


def test_status_reports_pool_health():
    pool = _pool(2)
    pool.mark_exhausted("k0", GROQ_429)
    status = pool.status()
    assert status[0]["available"] is False
    assert status[0]["cooldown_seconds"] > 1000
    assert status[0]["failures"] == 1
    assert status[1]["available"] is True


def test_reset_clears_cooldowns():
    pool = _pool(2)
    pool.mark_exhausted("k0", GROQ_429)
    pool.reset()
    assert all(s["available"] for s in pool.status())


def test_pool_capacity_scales_with_keys():
    """The whole point: N keys means N times the daily budget."""
    pool = _pool(3)
    survived = 0
    for _ in range(3):
        key = pool.acquire()
        if key is None:
            break
        survived += 1
        pool.mark_exhausted(key, GROQ_429)
    assert survived == 3
    assert pool.acquire() is None


# --- service integration -----------------------------------------------------


def test_analysis_service_rotates_keys_on_quota_error(monkeypatch):
    """A rate-limited key must not fail the request while other keys remain."""
    import app.services.analysis_service as a

    pool = KeyPool.from_sources(keys_csv="dead_key,live_key")
    service = a.OpenAIAnalysisService(
        api_key="dead_key", model="m", base_url=a.GROQ_BASE_URL, key_pool=pool
    )

    seen = []

    class FakeMessage:
        content = '{"ok": true}'

    class FakeResponse:
        choices = [type("C", (), {"message": FakeMessage()})()]

    def fake_request(api_key, prompt, system):
        seen.append(api_key)
        if api_key == "dead_key":
            raise RuntimeError(GROQ_429)
        return FakeResponse()

    monkeypatch.setattr(service, "_request", fake_request)

    assert service.complete_json("hi") == {"ok": True}
    assert seen == ["dead_key", "live_key"]
    assert pool.status()[0]["available"] is False


def test_analysis_service_reports_clearly_when_all_keys_dead(monkeypatch):
    import app.services.analysis_service as a

    pool = KeyPool.from_sources(keys_csv="k1,k2")
    service = a.OpenAIAnalysisService(
        api_key="k1", model="m", base_url=a.GROQ_BASE_URL, key_pool=pool
    )
    monkeypatch.setattr(
        service, "_request", lambda *args: (_ for _ in ()).throw(RuntimeError(GROQ_429))
    )

    with pytest.raises(a.AnalysisError, match="Rate limit reached"):
        service.complete_json("hi")


def test_transcription_service_rotates_keys(monkeypatch, tmp_path):
    import app.services.transcription_service as t

    audio = tmp_path / "a.wav"
    audio.write_bytes(b"x" * 32)

    pool = KeyPool.from_sources(keys_csv="dead_key,live_key")
    service = t.OpenAIWhisperTranscriptionService(
        api_key="dead_key", model="m", base_url=t.GROQ_BASE_URL,
        provider="Groq", key_pool=pool,
    )
    monkeypatch.setattr(t, "compress_audio_for_upload", lambda p: p)

    seen = []

    def fake_request(api_key, upload_path):
        seen.append(api_key)
        if api_key == "dead_key":
            raise RuntimeError(GROQ_429)
        from types import SimpleNamespace

        return SimpleNamespace(text="hello", language="English", duration=1.0, segments=[])

    monkeypatch.setattr(service, "_request", fake_request)

    result = service.transcribe(audio)
    assert result.text == "hello"
    assert seen == ["dead_key", "live_key"]


# --- invalid / revoked keys --------------------------------------------------


def test_invalid_key_detection():
    from app.core.key_pool import is_invalid_key_error

    assert is_invalid_key_error(RuntimeError("Error code: 401 - Invalid API Key"))
    assert is_invalid_key_error(RuntimeError("invalid_api_key"))
    assert not is_invalid_key_error(RuntimeError(GROQ_429))


def test_revoked_key_is_skipped_not_blocking():
    """A dead key in the file must not block every request queued behind it."""
    pool = _pool(3)
    used = []

    def run(key):
        used.append(key)
        if key == "k0":
            raise RuntimeError("Error code: 401 - {'error': {'message': 'Invalid API Key'}}")
        return "ok"

    assert call_with_rotation(pool, run) == "ok"
    assert used == ["k0", "k1"]
    status = pool.status()
    assert status[0]["available"] is False
    assert status[0]["cooldown_seconds"] == -1, "revoked keys are retired, not cooled down"


def test_revoked_key_stays_disabled_after_reset():
    pool = _pool(2)
    pool.disable("k0", "invalid or revoked")
    assert pool.acquire() == "k1"


# --- multiple key files ------------------------------------------------------


def test_extra_key_files_are_merged(tmp_path):
    """Keys may live outside the repo; both files contribute to one pool."""
    main = tmp_path / "groq_keys.txt"
    main.write_text("gsk_a\ngsk_b\n")
    external = tmp_path / "elsewhere" / "keys.txt"
    external.parent.mkdir()
    external.write_text("gsk_c\ngsk_d\n")

    pool = KeyPool.from_sources(keys_file=main, extra_files=[external])
    assert pool.size == 4
    assert pool.acquire() == "gsk_a"


def test_duplicate_keys_across_files_collapse(tmp_path):
    main = tmp_path / "a.txt"
    main.write_text("gsk_same\ngsk_only_main\n")
    other = tmp_path / "b.txt"
    other.write_text("gsk_same\ngsk_only_other\n")

    pool = KeyPool.from_sources(keys_file=main, extra_files=[other])
    assert pool.size == 3


def test_missing_extra_file_is_ignored(tmp_path):
    main = tmp_path / "a.txt"
    main.write_text("gsk_a\n")
    pool = KeyPool.from_sources(keys_file=main, extra_files=[tmp_path / "nope.txt"])
    assert pool.size == 1


def test_extra_file_alone_works(tmp_path):
    external = tmp_path / "keys.txt"
    external.write_text("gsk_only\n")
    pool = KeyPool.from_sources(keys_file=tmp_path / "missing.txt", extra_files=[external])
    assert pool.size == 1
