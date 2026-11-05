"""AURA OS Memory Vault."""

from typing import Optional

from aura.vault.vault import AREAS, Vault

_vault: Optional[Vault] = None


def get_vault() -> Vault:
    global _vault
    if _vault is None:
        from aura.core.config import AuraConfig

        _vault = Vault(AuraConfig.load().vault.path)
    return _vault


def set_vault(v: Vault) -> None:
    global _vault
    _vault = v


__all__ = ["Vault", "AREAS", "get_vault", "set_vault"]
