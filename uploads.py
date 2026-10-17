"""
uploads.py
----------
Opsyonal na cloud image storage (Cloudinary) gamit ang stdlib urllib --
walang third-party dependency (tugma sa style ng project).

Kapag naka-configure ang Cloudinary (CLOUDINARY_URL o CLOUDINARY_* env vars),
ang admin image uploads ay diretso sa cloud (para hindi mawala tuwing
redeploy sa online hosting na ephemeral ang disk). Kung wala, local disk
pa rin ang gamit.

Gamitin:
    import uploads
    if uploads.is_enabled():
        url = uploads.upload_bytes(data, "portfolio/abc123", "image/png")
"""

import base64
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from flask import current_app


class UploadError(Exception):
    """Hindi na-upload/nabura ang image sa cloud storage."""


def _settings():
    """Kunin ang (cloud_name, api_key, api_secret) mula config.
    Sinusuportahan ang CLOUDINARY_URL o hiwa-hiwalay na vars.
    Magbalik ng None kung hindi naka-configure."""
    cfg = current_app.config

    url = cfg.get("CLOUDINARY_URL")
    if url:
        # cloudinary://<api_key>:<api_secret>@<cloud_name>
        parsed = urllib.parse.urlparse(url)
        key = urllib.parse.unquote(parsed.username or "")
        secret = urllib.parse.unquote(parsed.password or "")
        cloud = parsed.hostname or ""
        if key and secret and cloud:
            return cloud, key, secret

    cloud = cfg.get("CLOUDINARY_CLOUD_NAME")
    key = cfg.get("CLOUDINARY_API_KEY")
    secret = cfg.get("CLOUDINARY_API_SECRET")
    if cloud and key and secret:
        return cloud, key, secret
    return None


def is_enabled():
    """Naka-configure ba ang Cloudinary?"""
    return _settings() is not None


def is_cloudinary_url(url):
    return bool(url) and "res.cloudinary.com/" in url


def _sign(params, secret):
    """Cloudinary signature: SHA1 ng sorted params + api_secret."""
    to_sign = "&".join(f"{k}={params[k]}" for k in sorted(params))
    return hashlib.sha1((to_sign + secret).encode("utf-8")).hexdigest()


def _post(url, form, timeout=60):
    body = urllib.parse.urlencode(form).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _public_id_from_url(url):
    """Kunin ang public_id mula sa Cloudinary secure_url."""
    marker = "/upload/"
    if not url or marker not in url:
        return None
    tail = url.split(marker, 1)[1].split("?", 1)[0].split("#", 1)[0]
    parts = tail.split("/")
    if parts and parts[0].startswith("v") and parts[0][1:].isdigit():
        parts = parts[1:]
    public_id = "/".join(parts)
    if "." in public_id.rsplit("/", 1)[-1]:
        public_id = public_id.rsplit(".", 1)[0]
    return public_id or None


def upload_bytes(data, public_id, content_type="image/jpeg"):
    """I-upload ang image bytes sa Cloudinary. Magbalik ng secure_url.
    Nagtataas ng UploadError kapag mabigo."""
    settings = _settings()
    if settings is None:
        raise UploadError("Cloudinary hindi naka-configure.")
    cloud, key, secret = settings

    file_param = "data:{};base64,{}".format(
        content_type or "image/jpeg",
        base64.b64encode(data).decode("ascii"),
    )
    timestamp = int(time.time())
    params = {"public_id": public_id, "timestamp": timestamp}
    form = {
        "file": file_param,
        "api_key": key,
        "public_id": public_id,
        "timestamp": timestamp,
        "signature": _sign(params, secret),
    }
    try:
        payload = _post(
            f"https://api.cloudinary.com/v1_1/{cloud}/image/upload", form
        )
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise UploadError(f"Cloudinary HTTP {e.code}: {detail}") from e
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise UploadError(str(e)) from e

    url = payload.get("secure_url") or payload.get("url")
    if not url:
        raise UploadError("Walang URL sa Cloudinary response.")
    return url


def delete_by_url(url):
    """Burahin ang image sa Cloudinary base sa secure_url nito."""
    settings = _settings()
    if settings is None:
        raise UploadError("Cloudinary hindi naka-configure.")
    cloud, key, secret = settings

    public_id = _public_id_from_url(url)
    if not public_id:
        raise UploadError("Hindi makuha ang public_id sa URL.")

    timestamp = int(time.time())
    params = {"public_id": public_id, "timestamp": timestamp}
    form = {
        "api_key": key,
        "public_id": public_id,
        "timestamp": timestamp,
        "signature": _sign(params, secret),
    }
    try:
        payload = _post(
            f"https://api.cloudinary.com/v1_1/{cloud}/image/destroy", form
        )
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise UploadError(str(e)) from e

    if payload.get("result") not in ("ok", "not found"):
        raise UploadError(f"Cloudinary destroy: {payload.get('result')}")
    return True
