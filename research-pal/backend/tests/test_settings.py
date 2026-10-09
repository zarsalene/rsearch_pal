"""Login and the choice of the AI."""
from app import llm


def test_login(client):
    assert client.get("/api/papers").status_code == 401
    assert client.post("/api/login", json={"password": "wrong"}).status_code == 401
    assert client.post("/api/login", json={"password": "test-password-123"}).json()["token"]


def test_wrong_password_is_limited(client):
    codes = [client.post("/api/login", json={"password": "wrong"}).status_code for _ in range(9)]
    assert codes[:8] == [401] * 8 and codes[8] == 429


def test_the_student_chooses_the_ai(client, auth_headers):
    """The order and the model of each provider. A wrong choice is refused. Keys never go through the page."""
    h = auth_headers
    assert client.get("/api/config", headers=h).json()["llm_ready"] is True
    cfg = client.get("/api/config", headers=h).json()
    assert cfg["ai_choice"]["primary"] == "gemini" and cfg["ai_choice"]["custom"] is False and {o["provider"] for o in cfg["ai_options"]} == {"gemini", "groq", "openrouter", "ollama"}
    assert "key" not in str(cfg["ai_options"]).lower().replace("ready", "")
    assert client.put("/api/ai", headers=h, json={"primary": "nope"}).status_code == 400
    assert client.put("/api/ai", headers=h, json={"primary": "groq", "models": {"groq": "bad model!"}}).status_code == 400
    cfg = client.put("/api/ai", headers=h, json={"primary": "groq", "fallbacks": ["gemini", "groq"], "models": {"groq": "openai/gpt-oss-20b"}}).json()
    assert cfg["ai_choice"] == {"primary": "groq", "fallbacks": ["gemini"], "models": {"groq": "openai/gpt-oss-20b", "gemini": "gemini-flash-latest"}, "custom": True}, cfg["ai_choice"]
    assert [p["provider"] for p in cfg["providers"]] == ["groq", "gemini"] and cfg["model"] == "openai/gpt-oss-20b"
    llm.load_choice()  # the choice is saved in the database: it is the same after a restart
    assert llm.choice()["primary"] == "groq"
    cfg = client.delete("/api/ai", headers=h).json()
    assert cfg["ai_choice"]["primary"] == "gemini" and cfg["ai_choice"]["custom"] is False
