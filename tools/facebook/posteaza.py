#!/usr/bin/env python3
"""Publică pe pagina de Facebook a școlii activitățile noi de pe site.

Rulează în GitHub Actions după fiecare publicare reușită a site-ului.
- Doar paginile din content/activitati/ și content/erasmus/ (fără _index.md).
- Documentele, avizierul și proiectele NU se publică pe Facebook.
- Se sare peste paginile care au deja câmpul `facebook:` (vin de pe Facebook)
  și peste cele din tools/facebook/postate.txt (deja publicate).
- O postare = textul activității + până la 10 poze + linkul spre pagina de pe site.

Variabile de mediu: FB_PAGE_ID, FB_PAGE_TOKEN, SITE_URL (implicit https://scoalaboldu.ro),
DRY_RUN=1 pentru probă (nu publică nimic, doar afișează).
"""
import io, json, os, re, sys, time
from pathlib import Path

import requests
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "tools/facebook/postate.txt"
SURSE = ["content/activitati", "content/erasmus"]
GRAPH = "https://graph.facebook.com/v21.0"
MAX_POZE = 10


def pagini():
    for s in SURSE:
        for p in sorted((ROOT / s).rglob("*.md")):
            if p.name != "_index.md":
                yield p


def citeste(p):
    t = p.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", t, re.S)
    if not m:
        return {}, t
    return yaml.safe_load(m.group(1)) or {}, m.group(2).strip()


def url_pagina(site, rel):
    # content/activitati/x.md -> /activitati/x/ ; content/erasmus/p/x.md -> /erasmus/p/x/
    sub = rel[len("content/"):-len(".md")]
    return f"{site.rstrip('/')}/{sub}/"


def text_simplu(md):
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"[*_`#>]+", "", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def jpeg(path):
    im = Image.open(path).convert("RGB")
    b = io.BytesIO()
    im.save(b, "JPEG", quality=88)
    return b.getvalue()


def cere(metoda, url, **kw):
    for incercare in range(3):
        r = requests.request(metoda, url, timeout=120, **kw)
        if r.status_code < 500:
            break
        time.sleep(5 * (incercare + 1))
    d = r.json()
    if "error" in d:
        raise RuntimeError(f"Facebook: {d['error'].get('message')}")
    return d


def main():
    site = os.environ.get("SITE_URL", "https://scoalaboldu.ro")
    dry = os.environ.get("DRY_RUN") == "1"
    page_id = os.environ.get("FB_PAGE_ID")
    token = os.environ.get("FB_PAGE_TOKEN")
    if not dry and not (page_id and token):
        print("Lipsesc FB_PAGE_ID / FB_PAGE_TOKEN – nu public nimic.")
        return
    postate = set(LEDGER.read_text(encoding="utf-8").split()) if LEDGER.exists() else set()
    noi = []
    for p in pagini():
        rel = p.relative_to(ROOT).as_posix()
        if rel in postate:
            continue
        fm, corp = citeste(p)
        if fm.get("facebook") or fm.get("draft"):
            postate.add(rel)  # vine deja de pe Facebook / ciornă: nu se publică
            continue
        noi.append((rel, fm, corp))

    for rel, fm, corp in noi:
        titlu = str(fm.get("title", "")).strip()
        perioada = str(fm.get("perioada", "")).strip()
        link = url_pagina(site, rel)
        mesaj = "\n\n".join(x for x in [titlu + (f" ({perioada})" if perioada else ""),
                                        text_simplu(corp),
                                        f"Detalii și galeria completă: {link}"] if x)
        poze = [fm["image"]] if fm.get("image") else []
        poze += list(fm.get("galerie") or [])
        poze = [ROOT / "assets" / x for x in poze if (ROOT / "assets" / x).exists()][:MAX_POZE]
        print(f"→ {rel}: {len(poze)} poze\n{mesaj}\n")
        if dry:
            continue
        media = []
        for f in poze:
            d = cere("POST", f"{GRAPH}/{page_id}/photos",
                     data={"published": "false", "access_token": token},
                     files={"source": (f.stem + ".jpg", jpeg(f), "image/jpeg")})
            media.append({"media_fbid": d["id"]})
        data = {"message": mesaj, "access_token": token}
        if media:
            for i, m in enumerate(media):
                data[f"attached_media[{i}]"] = json.dumps(m)
        else:
            data["link"] = link
        d = cere("POST", f"{GRAPH}/{page_id}/feed", data=data)
        print(f"  publicat: {d.get('id')}")
        postate.add(rel)
        LEDGER.write_text("\n".join(sorted(postate)) + "\n", encoding="utf-8")

    LEDGER.write_text("\n".join(sorted(postate)) + "\n", encoding="utf-8")
    print(f"Gata: {len(noi)} postări {'(probă)' if dry else ''}")


if __name__ == "__main__":
    main()
