"""Environment-variable credential source.

Users who don't want the tool to read their browser's cookie database can supply
cookies directly via env vars:

  RDT_COOKIE  — a full raw Cookie header ("a=1; b=2; ...")   [most robust]
  RDT_SESSION — just the reddit_session cookie value          [convenience]
  RDT_MODHASH — optional modhash (enables write actions)

Env credentials take priority over the saved file and over browser extraction,
and are used in-memory only (never written to disk).
"""

from __future__ import annotations

from rdt_cli import auth
from rdt_cli.auth import Credential

# ── parse_cookie_header ─────────────────────────────────────────────


class TestParseCookieHeader:
    def test_basic_pairs(self):
        assert auth.parse_cookie_header("a=1; b=2") == {"a": "1", "b": "2"}

    def test_strips_whitespace_and_skips_blanks(self):
        assert auth.parse_cookie_header("  a = 1 ;; b=2 ; ") == {"a": "1", "b": "2"}

    def test_value_may_contain_equals(self):
        # JWT/base64 values can contain '=' — split on the first '=' only.
        assert auth.parse_cookie_header("token_v2=ab.cd==; x=1") == {"token_v2": "ab.cd==", "x": "1"}

    def test_skips_pairs_without_name(self):
        assert auth.parse_cookie_header("=novalue; good=1") == {"good": "1"}

    def test_empty_returns_empty_dict(self):
        assert auth.parse_cookie_header("") == {}


# ── extract_env_credential ──────────────────────────────────────────


class TestExtractEnvCredential:
    def test_none_when_unset(self):
        assert auth.extract_env_credential() is None

    def test_rdt_cookie_raw_header(self, monkeypatch):
        monkeypatch.setenv("RDT_COOKIE", "reddit_session=abc; token_v2=xyz")
        cred = auth.extract_env_credential()
        assert cred is not None
        assert cred.cookies == {"reddit_session": "abc", "token_v2": "xyz"}
        assert cred.source == "env"

    def test_rdt_session_convenience(self, monkeypatch):
        monkeypatch.setenv("RDT_SESSION", "sessval")
        cred = auth.extract_env_credential()
        assert cred is not None
        assert cred.cookies["reddit_session"] == "sessval"

    def test_rdt_session_with_modhash_enables_write(self, monkeypatch):
        monkeypatch.setenv("RDT_SESSION", "sessval")
        monkeypatch.setenv("RDT_MODHASH", "mh123")
        cred = auth.extract_env_credential()
        assert cred.cookies["reddit_session"] == "sessval"
        assert cred.cookies["modhash"] == "mh123"

    def test_rdt_cookie_takes_precedence_and_session_overlays(self, monkeypatch):
        # RDT_COOKIE supplies the full set; RDT_SESSION overrides that one key.
        monkeypatch.setenv("RDT_COOKIE", "reddit_session=old; token_v2=xyz")
        monkeypatch.setenv("RDT_SESSION", "new")
        cred = auth.extract_env_credential()
        assert cred.cookies["reddit_session"] == "new"
        assert cred.cookies["token_v2"] == "xyz"

    def test_env_credential_is_not_persisted(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auth, "CONFIG_DIR", tmp_path)
        monkeypatch.setattr(auth, "CREDENTIAL_FILE", tmp_path / "credential.json")
        monkeypatch.setenv("RDT_SESSION", "sessval")

        auth.extract_env_credential()

        assert not (tmp_path / "credential.json").exists()


# ── get_credential chain: env → saved → browser ─────────────────────


class TestCredentialChainPriority:
    def test_env_beats_saved_file(self, monkeypatch):
        monkeypatch.setenv("RDT_SESSION", "from_env")
        monkeypatch.setattr(auth, "load_credential", lambda: Credential(cookies={"reddit_session": "from_file"}))

        cred = auth.get_credential()
        assert cred is not None
        assert cred.cookies["reddit_session"] == "from_env"
        assert cred.source == "env"

    def test_env_used_even_when_browser_disabled(self, monkeypatch):
        # Public commands pass allow_browser=False but should still honor env.
        monkeypatch.setenv("RDT_SESSION", "from_env")
        monkeypatch.setattr(auth, "load_credential", lambda: None)

        cred = auth.get_credential(allow_browser=False)
        assert cred is not None and cred.cookies["reddit_session"] == "from_env"

    def test_browser_is_last_resort(self, monkeypatch):
        # No env, no saved → browser extraction runs (kept, but last).
        monkeypatch.setattr(auth, "load_credential", lambda: None)
        called = {"n": 0}

        def spy():
            called["n"] += 1
            return Credential(cookies={"reddit_session": "from_browser"}, source="browser:chrome")

        monkeypatch.setattr(auth, "extract_browser_credential", spy)

        cred = auth.get_credential()
        assert cred.source == "browser:chrome"
        assert called["n"] == 1

    def test_env_short_circuits_before_browser(self, monkeypatch):
        monkeypatch.setenv("RDT_SESSION", "from_env")
        monkeypatch.setattr(auth, "load_credential", lambda: None)

        def boom():
            raise AssertionError("browser extraction must not run when env is set")

        monkeypatch.setattr(auth, "extract_browser_credential", boom)

        assert auth.get_credential().source == "env"


# ── capability: anonymous (token_v2) cookies count as read ──────────


class TestAnonymousCapability:
    def test_token_v2_only_is_read_capable(self):
        from rdt_cli.session import SessionState

        state = SessionState.from_credential(Credential(cookies={"token_v2": "anon"}, source="env"))
        assert state.is_authenticated is True   # "read" capability
        assert state.can_write is False
