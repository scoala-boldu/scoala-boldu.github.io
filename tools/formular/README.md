# Formularul „Activitate pentru site”

- Formular (orice cont Google cu link-ul; e-mailul celui care trimite se înregistrează): https://docs.google.com/forms/d/e/1FAIpQLSdwc12cbLrizsCxX0mFPfklYkzzvGjvcIkZjwWSqGShpHNZBA/viewform
- Răspunsuri (foaie): https://docs.google.com/spreadsheets/d/13HvMycTP1uyq1FFr8VreXV8tOrz_ZNyIlPVn1TifbPk/edit
- Poze încărcate (folder Drive, proprietar admin@scoalaboldu.ro, partajat cu negraru.sorin@gmail.com):
  https://drive.google.com/drive/folders/1GZCPT_G3kRQnt39gTIjmeCzctAoqX6PQ4TxSGlCYhU3XbpZaEGyeqf2uAoa5RAdEv8tJarVT

## Fluxul săptămânal (vineri seara)

1. Se citesc rândurile noi din foaie (marca temporală > ultima din `procesate.txt`).
2. Pentru fiecare rând se descarcă pozele din coloanele „Poze (1–10)” și „Poze (11–20)”.
3. `python3 tools/formular/proceseaza.py <folder_poze> raspuns.json` alege cele mai bune
   max. 15 poze (claritate, expunere, fără duplicate), le micșorează la 1400 px webp,
   șterge datele EXIF/GPS și creează pagina în colecția aleasă în formular.
4. Totul se pune pe o ramură `propuneri/AAAA-LL-ZZ` și se deschide un Pull Request.
5. Sorin primește rezumatul; **nimic nu se publică până nu aprobă** (merge în `main`).
6. Marca temporală a rândului se adaugă în `procesate.txt`.

`raspuns.json`: `titlu`, `data` (AAAA-LL-ZZ), `perioada`, `unde`, `clase`,
`coordonatori`, `descriere`, `facebook`, opțional `slug`.
