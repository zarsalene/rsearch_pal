"""Listen button. No test loads the real voice: a fake voice writes a short WAV."""
import wave

import pytest

from app import tts


class FakeVoice:
    def __init__(self):
        self.texts = []

    def synthesize_wav(self, text, w):
        self.texts.append(text)
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 160)


@pytest.fixture
def voice(monkeypatch):
    v = FakeVoice()
    monkeypatch.setattr(tts, "_voice", v)
    return v


def test_clean_removes_links_and_citation_numbers():
    assert tts.clean("See https://x.org/a  now [12] and [3, 4].") == "See now and ."


def test_clean_refuses_empty_text():
    with pytest.raises(tts.TTSError):
        tts.clean("  [1]  ")


def test_clean_cuts_a_long_text_at_a_sentence_end():
    out = tts.clean("Word. " * 1000)
    assert len(out) <= tts.MAX_CHARS and out.endswith(".")


def test_endpoint_returns_wav(client, auth_headers, voice):
    r = client.post("/api/tts", json={"text": "Hello world."}, headers=auth_headers)
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    assert r.content[:4] == b"RIFF" and voice.texts == ["Hello world."]


def test_endpoint_needs_login(client):
    assert client.post("/api/tts", json={"text": "Hi"}).status_code == 401


def test_endpoint_empty_text_is_400(client, auth_headers, voice):
    assert client.post("/api/tts", json={"text": " "}, headers=auth_headers).status_code == 400


def test_switch_off_gives_403(client, auth_headers, voice):
    client.put("/api/features", json={"features": {"tts": False}}, headers=auth_headers)
    assert client.post("/api/tts", json={"text": "Hi"}, headers=auth_headers).status_code == 403


def test_missing_package_gives_503(client, auth_headers, monkeypatch):
    monkeypatch.setattr(tts, "_voice", None)
    monkeypatch.setitem(__import__("sys").modules, "piper", None)
    r = client.post("/api/tts", json={"text": "Hi"}, headers=auth_headers)
    assert r.status_code == 503


def test_passages_join_hyphens_and_stay_short():
    out = tts.passages("The sys-\ntem works. " + "A sentence here. " * 200)
    assert out[0].startswith("The system works.")
    assert all(len(p) <= tts.MAX_CHARS for p in out) and len(out) > 1


def test_read_page_endpoint(client, auth_headers, sample_pdfs):
    from helpers import upload
    pid = upload(client, auth_headers, sample_pdfs["a.pdf"].path)
    r = client.get(f"/api/papers/{pid}/read/1", headers=auth_headers)
    assert r.status_code == 200 and r.json()["passages"]
    assert client.get(f"/api/papers/{pid}/read/99", headers=auth_headers).status_code == 404
