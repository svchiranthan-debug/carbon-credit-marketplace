"""SECRET_KEY: placeholder values are replaced by a random key persisted in backend/.env."""
from app import config


def test_placeholder_secret_is_replaced_and_persisted(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BACKEND_DIR", str(tmp_path))
    (tmp_path / ".env").write_text("CORS_ORIGINS=*\nSECRET_KEY=change-me\n")
    cfg = config.Settings(_env_file=None, SECRET_KEY="change-me")
    config._ensure_secret_key(cfg)
    assert cfg.SECRET_KEY not in config._PLACEHOLDER_SECRETS and len(cfg.SECRET_KEY) == 64
    lines = (tmp_path / ".env").read_text().splitlines()
    assert "CORS_ORIGINS=*" in lines
    assert [l for l in lines if l.startswith("SECRET_KEY=")] == [f"SECRET_KEY={cfg.SECRET_KEY}"]


def test_real_secret_is_left_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BACKEND_DIR", str(tmp_path))
    cfg = config.Settings(_env_file=None, SECRET_KEY="a-real-configured-key")
    config._ensure_secret_key(cfg)
    assert cfg.SECRET_KEY == "a-real-configured-key"
    assert not (tmp_path / ".env").exists()
