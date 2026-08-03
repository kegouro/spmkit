# Downloads

| File | Format | Size | Description |
|---|---|---:|---|
| [user-guide.pdf](../user-guide.pdf) | PDF | 115 KiB | 19-page printable manual |
| [user-guide.md](../user-guide.md) | Markdown / HTML | 55 KiB | Searchable web source rendered by this site |
| [user-guide.tex](https://github.com/kegouro/spmkit/blob/main/docs/user-guide.tex) | TeX source | 39 KiB | Reproducible PDF source |

**Documented source:** `0.1.5.dev0` · **GitHub release:** `0.1.4` ·
**PyPI distribution:** `0.1.2` · **Build date:** 2026-07-29

**Artifact identity:** Exact byte identities for the published manual artifacts
are recorded in the committed [content-addressed manifest](artifacts-manifest.json).
CI verifies the current files against that manifest. Git commits and release
tags identify repository revisions; the manifest proves exact artifact identity
only, not semantic correctness or reproducible PDF generation.

To compile the PDF from source:

```bash
latexmk -xelatex -interaction=nonstopmode -halt-on-error docs/user-guide.tex
```

The committed PDF is the publication artifact. A local rebuild can differ byte-for-byte
because the PDF embeds a creation timestamp; compare rendered content and page count in
addition to the published checksum.

---

[:material-book-open: Read HTML version](../user-guide.md) · [:material-file-pdf-box: Open PDF reader](reader.md)
