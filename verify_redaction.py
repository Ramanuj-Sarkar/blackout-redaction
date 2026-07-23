#!/usr/bin/env python3
"""
verify_redaction.py — independent check that PII is gone from a redacted PDF.

Usage:
    python3 verify_redaction.py file_redacted.pdf "Jane Doe" "00123456" "1980-01-01"

It searches the entire extracted text layer for each term you pass and reports
hits. Zero hits across all pages = the text was removed (not just covered).
For scanned/image pages it also flags whether any text layer exists at all.
"""
import sys, fitz

if len(sys.argv) < 2:
    sys.exit("Usage: python3 verify_redaction.py <pdf> [search terms...]")

path = sys.argv[1]
terms = sys.argv[2:]
doc = fitz.open(path)

full_text = ""
for i, page in enumerate(doc):
    full_text += page.get_text()

print(f"File: {path}")
print(f"Pages: {len(doc)}")
print(f"Total extractable characters: {len(full_text.strip())}")
print("-" * 50)

if terms:
    any_hit = False
    for t in terms:
        n = full_text.lower().count(t.lower())
        status = "STILL PRESENT  <-- FAILURE" if n else "not found (good)"
        if n:
            any_hit = True
        print(f"  '{t}': {n} hit(s) — {status}")
    print("-" * 50)
    print("RESULT:", "FAILED — redacted text still extractable" if any_hit
          else "PASSED — none of the terms remain in the text layer")
else:
    print("No search terms given. Dumping all extractable text so you can scan it:")
    print("-" * 50)
    print(full_text if full_text.strip() else "(no extractable text — likely a pure image/scan)")

doc.close()
