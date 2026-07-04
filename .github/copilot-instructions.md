# Copilot instructions for SplitVision

## Project purpose
SplitVision is a Windows desktop app for processing PDF files and splitting them into single-page PDFs. The main workflow is:
1. Load a PDF through the Tkinter UI or drag-and-drop.
2. Extract text from each page with PyPDF2 first.
3. Fall back to Windows native OCR when the expected pattern is not found.
4. Save the output pages and write a detailed log to the chosen output folder.

## Key implementation notes
- The main application lives in [splitvision.py](splitvision.py).
- The current architecture is designed to avoid external executables such as Tesseract or Poppler.
- OCR uses Windows native APIs through winocr and winrt. Do not reintroduce subprocess-based OCR tooling.
- PDF rendering is handled in-process with pypdfium2.
- The UI is Tkinter-based and should remain responsive while processing.

## Working conventions
- Preserve the existing drag-and-drop flow and the current log file format.
- Keep changes focused and minimal. Avoid unnecessary refactors.
- Do not modify generated artifacts under splitvision.build, splitvision.dist, or splitvision.onefile-build unless explicitly requested.
- Preserve the current behavior of naming output files based on detected document/OS patterns.

## Verification
After editing the app, verify with one of the following:
- python -m py_compile splitvision.py
- python splitvision.py

If you change packaging or dependencies, validate the build path with Nuitka as appropriate.
