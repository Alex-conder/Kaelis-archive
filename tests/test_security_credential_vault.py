"""
Credential vault tests
"""
import pytest
import tempfile
import shutil
import time
from pathlib import Path


class TestCredentialVault:
    @pytest.fixture
    def vault(self):
        tmpdir = tempfile.mkdtemp()
        from core.security.credential_vault import CredentialVault
        vault_path = Path(tmpdir) / "vault.enc"
        key_path = Path(tmpdir) / "master.key"
        v = CredentialVault(vault_path=str(vault_path), master_key_path=str(key_path))
        yield v
        time.sleep(0.1)
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_set_and_get(self, vault):
        vault.set("key1", "secret123")
        value = vault.get("key1")
        assert value == "secret123"

    def test_get_missing(self, vault):
        assert vault.get("none") is None

    def test_delete(self, vault):
        vault.set("k", "v")
        vault.delete("k")
        assert vault.get("k") is None

    def test_list_keys(self, vault):
        vault.set("a", "1")
        vault.set("b", "2")
        keys = vault.list_keys()
        assert sorted(keys) == ["a", "b"]

    def test_has_credential(self, vault):
        vault.set("k", "v")
        assert vault.has_credential("k") is True
        assert vault.has_credential("missing") is False

    def test_store_and_retrieve(self, vault):
        vault.store_credential("user1", "provider_a", "credential_data")
        assert vault.retrieve_credential("user1", "provider_a") == "credential_data"

    def test_delete_credential(self, vault):
        from core.security.credential_vault import CredentialNotFoundError
        vault.store_credential("user1", "provider_a", "credential_data")
        vault.delete_credential("user1", "provider_a")
        with pytest.raises(CredentialNotFoundError):
            vault.retrieve_credential("user1", "provider_a")

    def test_list_services(self, vault):
        vault.store_credential("user1", "svc1", "v")
        vault.store_credential("user1", "svc2", "v")
        services = vault.list_services("user1")
        assert "svc1" in services
        assert "svc2" in services


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
