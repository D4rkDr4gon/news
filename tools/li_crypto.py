#!/usr/bin/env python3
"""Cifrado de los borradores de LinkedIn del portal /news.

AES-256-GCM con clave PBKDF2-SHA256 (600k iteraciones) derivada de "LI_USER:LI_PASS".
Compatible con WebCrypto (index.html descifra en el navegador).

Uso:
  li_crypto.py history                      -> imprime el historial descifrado ([] si no existe)
  li_crypto.py decrypt <archivo.enc.json>   -> imprime el JSON descifrado
  li_crypto.py publish <FECHA> <post.json> <imagen.png>
      post.json = {"pilar","tema","angulo","hook","texto","hashtags":[...]}
      Escribe linkedin/FECHA.enc.json, agrega la entrada a linkedin/history.enc.json
      y BORRA post.json e imagen.png (no deben quedar en claro en el repo).
"""
import base64, json, os, sys
from pathlib import Path

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
except ImportError:
    sys.exit("Falta 'cryptography': pip install cryptography")

ITER = 600_000
ROOT = Path(__file__).resolve().parent.parent
LI = ROOT / "linkedin"
HIST = LI / "history.enc.json"
b64e = lambda b: base64.b64encode(b).decode()
b64d = base64.b64decode


def secret() -> bytes:
    u, p = os.environ.get("LI_USER"), os.environ.get("LI_PASS")
    if not u or not p:
        sys.exit("Faltan las variables de entorno LI_USER / LI_PASS")
    return f"{u}:{p}".encode()


def key(salt: bytes) -> bytes:
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(secret())


def encrypt(obj) -> dict:
    salt, iv = os.urandom(16), os.urandom(12)
    ct = AESGCM(key(salt)).encrypt(iv, json.dumps(obj, ensure_ascii=False).encode(), None)
    return {"v": 1, "kdf": "pbkdf2-sha256", "iter": ITER, "salt": b64e(salt), "iv": b64e(iv), "ct": b64e(ct)}


def decrypt(env: dict):
    k = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b64d(env["salt"]), iterations=env.get("iter", ITER)).derive(secret())
    return json.loads(AESGCM(k).decrypt(b64d(env["iv"]), b64d(env["ct"]), None))


def load(path: Path, default=None):
    if not path.exists():
        return default
    return decrypt(json.loads(path.read_text()))


def save(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(encrypt(obj)) + "\n")


def main(a):
    if a[:1] == ["history"]:
        print(json.dumps(load(HIST, []), ensure_ascii=False, indent=2))
    elif a[:1] == ["decrypt"] and len(a) == 2:
        print(json.dumps(load(Path(a[1])), ensure_ascii=False, indent=2))
    elif a[:1] == ["publish"] and len(a) == 4:
        date, post_p, png_p = a[1], Path(a[2]), Path(a[3])
        post = json.loads(post_p.read_text())
        for f in ("pilar", "tema", "texto"):
            if not post.get(f):
                sys.exit(f"post.json sin campo '{f}'")
        png = png_p.read_bytes()
        if png[:8] != b"\x89PNG\r\n\x1a\n":
            sys.exit("La imagen no es un PNG válido")
        save(LI / f"{date}.enc.json", {**post, "date": date, "png": b64e(png)})
        hist = [h for h in load(HIST, []) if h.get("date") != date]
        hist.insert(0, {"date": date, **{k: post.get(k, "") for k in ("pilar", "tema", "angulo", "hook")}})
        save(HIST, hist)
        post_p.unlink(); png_p.unlink()
        print(f"OK linkedin/{date}.enc.json ({len(png)//1024} KB de imagen) · historial: {len(hist)} posts")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception as e:
        if type(e).__name__ == "InvalidTag":
            sys.exit("No se pudo descifrar: LI_USER/LI_PASS no coinciden con los usados para cifrar")
        raise
