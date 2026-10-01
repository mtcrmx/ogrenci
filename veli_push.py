"""Veli telefon bildirimleri — VAPID anahtarı ve Web Push gönderimi."""
from __future__ import annotations

import json


def _pem_ise_der_yap(priv: str) -> str:
    if "BEGIN" not in priv:
        return priv
    import base64
    from cryptography.hazmat.primitives import serialization

    anahtar = serialization.load_pem_private_key(priv.encode(), password=None)
    return base64.urlsafe_b64encode(anahtar.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )).decode().rstrip("=")


def vapid_public_key() -> str:
    from database import admin_meta_get, admin_meta_set

    pub = admin_meta_get("vapid_public", "")
    if pub:
        priv = admin_meta_get("vapid_private", "")
        if "BEGIN" in priv:
            admin_meta_set("vapid_private", _pem_ise_der_yap(priv))
        return pub
    priv, pub = _vapid_uret()
    if not pub:
        return ""
    admin_meta_set("vapid_private", priv)
    admin_meta_set("vapid_public", pub)
    if not admin_meta_get("vapid_mailto", ""):
        admin_meta_set("vapid_mailto", "mailto:takip@akademipuan.com")
    return pub


def _vapid_uret() -> tuple[str, str]:
    try:
        import base64
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        return "", ""
    anahtar = ec.generate_private_key(ec.SECP256R1())
    priv = base64.urlsafe_b64encode(anahtar.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )).decode().rstrip("=")
    pub_ham = anahtar.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    pub = base64.urlsafe_b64encode(pub_ham).decode().rstrip("=")
    return priv, pub


def veli_push_gonder(ogrenci_id: int, metin: str, tur: str, url: str = "/veli") -> None:
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        return
    from database import admin_meta_get, veli_push_abonelikler, veli_push_sil

    priv = admin_meta_get("vapid_private", "")
    if not priv:
        vapid_public_key()
        priv = admin_meta_get("vapid_private", "")
    if not priv:
        return
    if "BEGIN" in priv:
        from database import admin_meta_set
        priv = _pem_ise_der_yap(priv)
        admin_meta_set("vapid_private", priv)
    baslik = {
        "uyari": "Uyarı",
        "olumlu": "Olumlu not",
        "odev": "Ödev",
        "duyuru": "Duyuru",
    }.get(tur, "Öğrenci takip")
    payload = json.dumps(
        {
            "baslik": baslik,
            "metin": metin or "Yeni bir mesaj var.",
            "tur": tur or "duyuru",
            "url": url if url.startswith("/veli") and not url.startswith("//") else "/veli",
        },
        ensure_ascii=False,
    )
    claims = {"sub": admin_meta_get("vapid_mailto", "mailto:takip@akademipuan.com")}
    for abone in veli_push_abonelikler(int(ogrenci_id)):
        try:
            webpush(
                subscription_info={
                    "endpoint": abone["endpoint"],
                    "keys": {"p256dh": abone["p256dh"], "auth": abone["auth"]},
                },
                data=payload,
                vapid_private_key=priv,
                vapid_claims=claims,
                ttl=86400,
                timeout=8,
                headers={"Urgency": "high", "Topic": "veli-haber"},
            )
        except WebPushException as exc:
            kod = getattr(getattr(exc, "response", None), "status_code", 0)
            if kod in {404, 410}:
                veli_push_sil(abone["endpoint"])
        except Exception:
            pass
