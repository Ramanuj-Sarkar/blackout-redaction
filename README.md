# Description

This file creates a GUI where PDFs can be redacted by drawing black boxes on them.

It also removes metadata from the files.

# How to Use

Start by running:

```bash
uv run redact_local.py
```

Once the GUI opens, click the "Open PDF" button to open a local PDF.

Use the "Prev" and "Next" buttons to go between pages of the PDF.

Click and drag to create a red rectangle which is a preview of the black rectangle which will occur.

Click "Undo Last Box" to undo the last box preview put on that page (but not on another page).

Click "Clear Page" to remove all box previews from that page.

Once all the boxes have been put down, click "Apply and Save" to actually draw the boxes on a new file with the filename of the original that has ```_redacted``` appended to the end.

You have to draw at least one box or the new file won't be created.
