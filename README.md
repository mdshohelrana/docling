# Docling Document Processor

A powerful yet simple Python script to convert documents (PDF, DOCX, PPTX, XLSX, CSV, URLs) to Markdown using [Docling](https://github.com/docling-project/docling).

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📄 **Multiple Formats** | PDF, DOCX, PPTX, XLSX, CSV, URLs |
| 🔒 **Password-Protected PDFs** | Handles encrypted documents seamlessly |
| 🔍 **OCR Support** | Extract text from scanned documents |
| 📁 **Directory Processing** | Process entire folders at once |
| 🔄 **Recursive Mode** | Include subdirectories automatically |
| ⚡ **Batch Processing** | Handle multiple files in one command |
| 🎯 **Simple & Clean** | Single Python file, minimal configuration |

---

## 📦 Installation

### Quick Setup (Recommended)

```bash
# Clone or download this repository
cd docling

# setup
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Requirements

- Python 3.8 or higher
- Dependencies: `docling`, `pypdf`

---

## 🚀 Quick Start

### Basic Usage

```bash
# Activate virtual environment (if not already activated)
source venv/bin/activate

# Process a single file
python processor.py document.pdf

# Process multiple files
python processor.py file1.pdf file2.docx file3.pptx

# Process entire directory
python processor.py test_docs/

# Process directory recursively (including subdirectories)
python processor.py test_docs/ --recursive
```

### With Options

```bash
# Password-protected PDF
python processor.py encrypted.pdf --password yourpassword

# Custom output directory
python processor.py document.pdf --output-dir ./converted

# Force OCR for scanned documents
python processor.py scanned.pdf --force-ocr

# Verbose logging for debugging
python processor.py document.pdf --verbose

# Combine multiple options
python processor.py test_docs/ --recursive --output-dir ./results --verbose
```

---

## 📖 Usage Examples

### 1. Single File Processing

```bash
python processor.py sample.pdf
```

**Output:**
```
INFO - Processing 1 document(s)...
INFO - Processing: sample.pdf
INFO - Document type: pdf
INFO - Converting document...
INFO - ✓ Successfully saved: output/sample.md
```

### 2. Password-Protected PDF

```bash
python processor.py test_docs/file-sample_protected.pdf --password 123
```

**Output:**
```
INFO - Document is password-protected: file-sample_protected.pdf
INFO - Successfully decrypted
INFO - ✓ Successfully saved: output/file-sample_protected.md
```

### 3. Directory Processing

```bash
python processor.py test_docs/
```

**Output:**
```
INFO - Processing 7 document(s)...
[1/7] Processing: test_docs/sample.pdf
[2/7] Processing: test_docs/file-sample.pdf
[3/7] Processing: test_docs/file_docs.docx
[4/7] Processing: test_docs/presentation.pptx
[5/7] Processing: test_docs/spreadsheet.xlsx
[6/7] Processing: test_docs/data.csv
[7/7] Processing: test_docs/file-sample_protected.pdf (skipped - no password)
Processing complete: 6/7 successful
```

> **Note:** Password-protected files are skipped unless you provide `--password` option.

### 4. Batch Processing with Mixed Formats

```bash
python processor.py report.pdf slides.pptx data.xlsx info.csv
```

---

## 🧪 Test Documents

The `test_docs/` directory contains sample files for testing:

```
test_docs/
├── sample.pdf                    # Regular PDF (4.1 MB)
├── file-sample.pdf               # Regular PDF (139 KB)
├── file-sample_protected.pdf     # Password-protected PDF (password: 123)
├── file_docs.docx                # Word document (109 KB)
├── presentation.pptx             # PowerPoint file (59 KB)
├── spreadsheet.xlsx              # Excel file (7.2 KB)
└── data.csv                      # CSV file (251 B)
```

### Try the Test Files

```bash
# Test all formats (including all types)
python processor.py test_docs/

# Test password-protected PDF
python processor.py test_docs/file-sample_protected.pdf --password 123

# Test Word document
python processor.py test_docs/file_docs.docx

# Test specific format (PowerPoint)
python processor.py test_docs/presentation.pptx

# Test multiple files at once
python processor.py test_docs/sample.pdf test_docs/file_docs.docx test_docs/spreadsheet.xlsx
```

---

## ⚙️ CLI Options

```
Usage: python processor.py [files/directories...] [options]

Positional Arguments:
  inputs                    Path(s) to file(s), directory, or URL(s)

Options:
  -o, --output-dir DIR      Output directory for markdown files
                            (default: ./output)
  
  -p, --password PASS       Password for encrypted/restricted PDFs
  
  --force-ocr              Force OCR processing for scanned documents
  
  -r, --recursive          Recursively process subdirectories
  
  -v, --verbose            Enable verbose logging for debugging
  
  -h, --help               Show help message and exit
```

---

## 📂 Project Structure

```
docling/
│
├── processor.py              # Main module (CLI + API)
│   ├── Configuration and types
│   ├── DoclingProcessor
│   ├── collect_files_from_directory
│   └── main() CLI entrypoint
│
├── test_docs/                 # Sample test documents
│   ├── README.md             # Test docs guide
│   ├── sample.pdf            # Regular PDF
│   ├── encrypted.pdf         # Password-protected PDF
│   ├── presentation.pptx     # PowerPoint
│   ├── spreadsheet.xlsx      # Excel
│   └── data.csv             # CSV
│
├── output/                    # Generated markdown files (created automatically)
│
├── requirements.txt           # Python dependencies
├── README.md                 # This file
```

---

## 💻 Programmatic Usage

You can also use the processor in your Python code:

```python
from pathlib import Path
from processor import DoclingProcessor, ProcessingConfig, ProcessorError

# Basic usage (raises ProcessorError if Docling is not installed or output dir is unusable)
processor = DoclingProcessor()
output_path = processor.process_document('document.pdf')
print(f"Saved to: {output_path}")

# With custom configuration
config = ProcessingConfig(
    output_dir=Path('./my_output'),
    password='secret123',
    force_ocr=True,
    verbose=True
)
processor = DoclingProcessor(config)

# Batch processing
files = ['file1.pdf', 'file2.docx', 'file3.pptx']
results = processor.process_batch(files)

# Check results
for input_file, output_file in results.items():
    if output_file:
        print(f"✓ {input_file} → {output_file}")
    else:
        print(f"✗ {input_file} (failed)")
```

---

## 🔧 Configuration

Default settings are defined at the top of `processor.py`:

```python
# Default output directory
DEFAULT_OUTPUT_DIR = './output'

# Output file extension
OUTPUT_EXTENSION = '.md'

# Supported file extensions
EXTENSIONS_PDF = ('.pdf',)
EXTENSIONS_DOCX = ('.docx', '.doc')
EXTENSIONS_PPTX = ('.pptx', '.ppt')
EXTENSIONS_XLSX = ('.xlsx', '.xls')
EXTENSIONS_CSV = ('.csv',)

# URL protocols
URL_PROTOCOLS = ('http://', 'https://')

# Logging format
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

# Display symbols
SYMBOL_SUCCESS = "✓"
SEPARATOR = "=" * 60
```

**Customization Example:**

```python
# Change output directory
DEFAULT_OUTPUT_DIR = '/data/converted'

# Change success symbol
SYMBOL_SUCCESS = "✔️"

# Customize separator
SEPARATOR = "-" * 80
```

---

## 📊 Supported Formats

| Format | Extensions | Features |
|--------|-----------|----------|
| **PDF** | `.pdf` | ✅ Regular<br>✅ Password-protected<br>✅ Scanned (with OCR) |
| **Word** | `.docx`, `.doc` | ✅ All Word documents |
| **PowerPoint** | `.pptx`, `.ppt` | ✅ Presentations |
| **Excel** | `.xlsx`, `.xls` | ✅ Spreadsheets (converted to tables) |
| **CSV** | `.csv` | ✅ Data files |
| **URLs** | `http://`, `https://` | ✅ Remote documents |

---

## 🛠️ Troubleshooting

### Issue: "Docling is not installed"

```bash
pip install docling
```

### Issue: Password-protected PDF fails

```bash
# Make sure to provide the password
python processor.py encrypted.pdf --password yourpassword
```

### Issue: OCR not working on scanned PDFs

```bash
# Force OCR mode
python processor.py scanned.pdf --force-ocr
```

### Issue: Need more debugging information

```bash
# Enable verbose logging
python processor.py document.pdf --verbose
```

### Issue: pypdf not found (for encrypted PDFs)

```bash
pip install pypdf
```

---

## 🎯 Use Cases

- **Document Conversion**: Convert reports, presentations, spreadsheets to Markdown
- **Content Migration**: Batch convert documentation for wikis or static sites
- **Data Extraction**: Extract text from scanned PDFs with OCR
- **Automated Workflows**: Integrate into CI/CD pipelines
- **Archive Processing**: Convert entire directories of documents

---

## 📝 Output Format

All documents are converted to clean Markdown format:

**Example PDF → Markdown:**
```markdown
# Document Title

## Section 1
Content here...

## Section 2
More content...
```

**Example Excel → Markdown:**
```markdown
| Name | Email | Department |
|------|-------|-----------|
| John | john@example.com | Engineering |
| Jane | jane@example.com | Marketing |
```

---

## 🤝 Contributing

Contributions welcome! This is a simple, single-file script designed to be:
- Easy to understand
- Easy to modify
- Easy to extend

Feel free to:
- Add new features
- Improve error handling
- Add support for new formats
- Enhance documentation

---

## 📄 License

MIT License - Free to use and modify

---

## 🔗 Resources

- [Docling Documentation](https://github.com/docling-project/docling)
- [Docling PyPI](https://pypi.org/project/docling/)
- [pypdf Documentation](https://pypdf.readthedocs.io/)

---

## 💡 Tips

1. **Performance**: Processing large PDFs may take time, especially with OCR enabled
2. **Memory**: Large batch operations may require sufficient RAM
3. **Passwords**: Store passwords securely, not in scripts or version control
4. **Output**: Check the `output/` directory for converted markdown files
5. **Logs**: Use `--verbose` flag for detailed processing information

---

**Made with ❤️ using Docling**
