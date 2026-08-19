# PrentenDF

A PDF geometry normalization tool designed to diagnose and repair
Fake-Landscape PDF pages caused by incorrect /Rotate metadata and broken
Page / Annotation / Stamp coordinate synchronization.

---

## Features & Usage

### Features

This tool diagnoses and repairs the following PDF geometry problems:

- Fake-Landscape pages caused by incorrect /Rotate metadata  
- Desynchronized Page / Annotation / Stamp coordinate systems  
- Mixed-orientation PDFs (partially correct, partially broken)

---

### Basic Usage

1. Diagnose a PDF and see which fix (if any) it needs:
   ```
   python main.py analyze input.pdf
   ```
2. Fix a Fake-Landscape page (Portrait MediaBox + /Rotate=270):
   ```
   python main.py fix-fake-landscape input.pdf output.pdf
   ```
3. Fix a Fake-Portrait page (Landscape MediaBox + /Rotate=90):
   ```
   python main.py fix-fake-portrait input.pdf output.pdf
   ```

---

## Installation & Tech Stack

### Setup
```
pip install -r requirements.txt
```
---

### Tech Stack

| Technology | Version |
|------------|---------|
| Python | 3.13 |
| pypdf | 6.1.0 |

### Testing

1. Diagnose a PDF and see which fix (if any) it needs:
   ```
   python main.py analyze input.pdf
   ```
2. Fix a Fake-Landscape page (Portrait MediaBox + /Rotate=270):
   ```
   python main.py fix-fake-landscape input.pdf output.pdf
   ```
3. Fix a Fake-Portrait page (Landscape MediaBox + /Rotate=90):
   ```
   python main.py fix-fake-portrait input.pdf output.pdf
   ```
