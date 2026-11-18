#!/usr/bin/env python3
"""Procesează o trimitere din formularul „Activitate pentru site”.

Intrare: un folder cu pozele trimise + un fișier raspuns.json cu câmpurile din foaia
de răspunsuri. Ieșire: pozele selectate (webp 1400px, fără EXIF/GPS) în
assets/images/foto/formular/<slug>/ și pagina .md în colecția potrivită.

Selecția: elimină pozele neclare, prea întunecate/arse și duplicatele aproape
identice, apoi păstrează cele mai bune MAX_POZE (implicit 15), în ordine cronologică.

Utilizare:
  python3 tools/formular/proceseaza.py <folder_poze> <raspuns.json> [--max 15] [--repo .]
"""
import argparse, json, re, sys, unicodedata, datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, ExifTags

COLECTII = {
    "Activități": "content/activitati",
    "Erasmus+ · Conectează-te digital (2026–2028)": "content/erasmus/conecteaza-te-digital",
    "Erasmus+ · Pasiune pentru mediu (2025–2026)": "content/erasmus/pasiune-pentru-mediu",
    "Erasmus+ · alt proiect": "content/erasmus",
    "Avizier (anunț)": "content/avizier",
}
EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
LUNI = ["ianuarie", "februarie", "martie", "aprilie", "mai", "iunie", "iulie",
        "august", "septembrie", "octombrie", "noiembrie", "decembrie"]


def slugify(text):
    t = unicodedata.normalize("NFKD", text.replace("ș", "s").replace("ț", "t")
                              .replace("Ș", "S").replace("Ț", "T"))
    t = t.encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:60]


def deschide(p):
    if p.suffix.lower() in {".heic", ".heif"}:
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            print(f"  ! sar peste {p.name}: lipsește pillow-heif", file=sys.stderr)
            return None
    try:
        im = Image.open(p)
        data = None
        try:
            exif = im.getexif()
            dt = exif.get(36867) or exif.get_ifd(0x8769).get(36867) or exif.get(306)
            if dt:
                data = datetime.datetime.strptime(str(dt)[:19], "%Y:%m:%d %H:%M:%S")
        except Exception:
            pass
        im = ImageOps.exif_transpose(im).convert("RGB")
        return im, data
    except Exception as e:
        print(f"  ! nu pot deschide {p.name}: {e}", file=sys.stderr)
        return None


def scoruri(im):
    g = np.asarray(im.convert("L").resize((512, int(512 * im.height / im.width) or 1)), dtype=np.float32)
    lap = (g[1:-1, 1:-1] * 4 - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:])
    claritate = float(lap.var())
    medie = float(g.mean())
    arse = float((g > 250).mean())
    negre = float((g < 5).mean())
    expunere = 1.0 - min(1.0, abs(medie - 125) / 125) - arse - negre
    rezolutie = min(1.0, (im.width * im.height) / (1600 * 1200))
    return claritate, expunere, rezolutie


def dhash(im, n=8):
    g = np.asarray(im.convert("L").resize((n + 1, n)), dtype=np.int16)
    return (g[:, 1:] > g[:, :-1]).flatten()


def selecteaza(poze, maxim):
    cl = np.array([p["claritate"] for p in poze])
    # claritate normalizată pe log, relativ la setul trimis
    lc = np.log1p(cl)
    norm = (lc - lc.min()) / (lc.max() - lc.min() + 1e-9)
    for p, c in zip(poze, norm):
        p["scor"] = 0.55 * c + 0.30 * max(0, p["expunere"]) + 0.15 * p["rezolutie"]
    # elimină clar ratatele (cele mai neclare 15% sub prag absolut, expunere proastă)
    bune = [p for p in poze if not (p["claritate"] < 15 or p["expunere"] < 0.15)]
    if len(bune) < min(4, len(poze)):
        bune = list(poze)
    bune.sort(key=lambda p: -p["scor"])
    alese = []
    for p in bune:
        if any((p["hash"] != a["hash"]).sum() <= 6 for a in alese):
            p["motiv"] = "duplicat"
            continue
        alese.append(p)
        if len(alese) >= maxim:
            break
    alese.sort(key=lambda p: (p["data"] or datetime.datetime.max, p["nume"]))
    return alese


def data_ro(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} {LUNI[d.month - 1]} {d.year}"


def yaml_str(s):
    return "'" + s.replace("'", "''") + "'"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("poze")
    ap.add_argument("raspuns")
    ap.add_argument("--max", type=int, default=15)
    ap.add_argument("--repo", default=".")
    a = ap.parse_args()

    r = json.loads(Path(a.raspuns).read_text(encoding="utf-8"))
    repo = Path(a.repo)
    titlu = r["titlu"].strip()
    data = r["data"]  # AAAA-LL-ZZ
    slug = r.get("slug") or f"{slugify(titlu)}-{data[:4]}"
    colectie = COLECTII.get(r.get("unde", "Activități"), "content/activitati")

    fisiere = sorted(p for p in Path(a.poze).rglob("*") if p.suffix.lower() in EXT)
    poze = []
    for f in fisiere:
        rez = deschide(f)
        if not rez:
            continue
        im, dt = rez
        c, e, rz = scoruri(im)
        poze.append(dict(nume=f.name, cale=f, im=im, data=dt, claritate=c,
                         expunere=e, rezolutie=rz, hash=dhash(im)))
    if not poze:
        sys.exit("Nicio poză validă.")
    alese = selecteaza(poze, a.max)

    dest = repo / "assets/images/foto/formular" / slug
    dest.mkdir(parents=True, exist_ok=True)
    cai = []
    for i, p in enumerate(alese, 1):
        im = p["im"]
        if im.width > 1400:
            im = im.resize((1400, round(im.height * 1400 / im.width)), Image.LANCZOS)
        nume = f"{data}-{i:02d}.webp"
        im.save(dest / nume, "WEBP", quality=78, method=6)  # fără exif → fără GPS
        cai.append(f"images/foto/formular/{slug}/{nume}")

    perioada = (r.get("perioada") or "").strip() or data_ro(data)
    fm = ["---", f"title: {yaml_str(titlu)}", f"date: '{data}'", f"perioada: {yaml_str(perioada)}"]
    if cai:
        fm.append(f"image: {cai[0]}")
        if len(cai) > 1:
            fm.append("galerie:")
            fm += [f"- {c}" for c in cai[1:]]
    if r.get("facebook"):
        fm.append(f"facebook: {r['facebook'].strip()}")
    fm.append("---")
    corp = r.get("descriere", "").strip()
    extra = []
    if r.get("clase"):
        extra.append(f"**Clase participante:** {r['clase'].strip()}")
    if r.get("coordonatori"):
        extra.append(f"**Coordonator(i):** {r['coordonatori'].strip()}")
    pagina = "\n".join(fm) + "\n\n" + corp + ("\n\n" + "  \n".join(extra) if extra else "") + "\n"

    out = repo / colectie / f"{slug}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pagina, encoding="utf-8")

    raport = {
        "pagina": str(out.relative_to(repo)), "trimise": len(fisiere), "valide": len(poze),
        "alese": [p["nume"] for p in alese],
        "respinse": [{"nume": p["nume"], "motiv": p.get("motiv") or "calitate/peste limită",
                      "scor": round(p["scor"], 2)} for p in poze if p not in alese],
    }
    print(json.dumps(raport, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
