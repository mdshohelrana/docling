"""Convert documents to Markdown using Docling (CLI and programmatic API)."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
except ImportError as _e:  # pragma: no cover - exercised when docling missing
    DocumentConverter = None  # type: ignore[misc, assignment]
    InputFormat = None  # type: ignore[misc, assignment]
    PdfFormatOption = None  # type: ignore[misc, assignment]
    PdfPipelineOptions = None  # type: ignore[misc, assignment]
    _DOCLING_IMPORT_ERROR = _e
else:
    _DOCLING_IMPORT_ERROR = None

if TYPE_CHECKING:
    from docling.document_converter import DocumentConverter as DocumentConverterType

# --- Configuration (defaults) ---
DEFAULT_OUTPUT_DIR = "./output"
OUTPUT_EXTENSION = ".md"
EXTENSIONS_PDF = (".pdf",)
EXTENSIONS_DOCX = (".docx", ".doc")
EXTENSIONS_PPTX = (".pptx", ".ppt")
EXTENSIONS_XLSX = (".xlsx", ".xls")
EXTENSIONS_CSV = (".csv",)
URL_PROTOCOLS = ("http://", "https://")
ALL_EXTENSIONS = (
    EXTENSIONS_PDF
    + EXTENSIONS_DOCX
    + EXTENSIONS_PPTX
    + EXTENSIONS_XLSX
    + EXTENSIONS_CSV
)

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
SYMBOL_SUCCESS = "✓"
SEPARATOR = "=" * 60

__all__ = [
    "DoclingProcessor",
    "ProcessingConfig",
    "DocumentType",
    "ProcessorError",
    "collect_files_from_directory",
    "main",
]


class DocumentType(Enum):
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    CSV = "csv"
    URL = "url"
    UNKNOWN = "unknown"


class ProcessorError(Exception):
    """Recoverable processing error (wrong type, missing file, bad password, etc.)."""


@dataclass
class ProcessingConfig:
    output_dir: Path = field(default_factory=lambda: Path(DEFAULT_OUTPUT_DIR))
    password: Optional[str] = None
    force_ocr: bool = False
    verbose: bool = False


def _ensure_docling_loaded() -> None:
    if _DOCLING_IMPORT_ERROR is not None:
        raise ProcessorError(
            "Docling is not installed. Install with: pip install docling"
        ) from _DOCLING_IMPORT_ERROR


def _pdf_is_encrypted(path: str) -> bool:
    if not pypdf:
        return False
    try:
        with open(path, "rb") as f:
            return bool(pypdf.PdfReader(f).is_encrypted)
    except OSError:
        raise
    except Exception as exc:  # pypdf may raise on corrupt PDF
        raise ProcessorError(f"Could not read PDF for encryption check: {exc}") from exc


class DoclingProcessor:
    """Convert documents to markdown using Docling."""

    def __init__(self, config: Optional[ProcessingConfig] = None) -> None:
        _ensure_docling_loaded()
        self.config = config or ProcessingConfig()
        self.logger = self._setup_logger()
        self._ensure_output_directory()

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(logging.DEBUG if self.config.verbose else logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(logging.Formatter(LOG_FORMAT))
            logger.addHandler(handler)
        return logger

    def _ensure_output_directory(self) -> None:
        try:
            self.config.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ProcessorError(
                f"Cannot create output directory {self.config.output_dir}: {exc}"
            ) from exc
        self.logger.info("Output directory: %s", self.config.output_dir.resolve())

    @staticmethod
    def _detect_document_type(input_path: str) -> DocumentType:
        lower = input_path.lower()
        if lower.startswith(URL_PROTOCOLS):
            return DocumentType.URL
        if lower.endswith(EXTENSIONS_PDF):
            return DocumentType.PDF
        if lower.endswith(EXTENSIONS_DOCX):
            return DocumentType.DOCX
        if lower.endswith(EXTENSIONS_PPTX):
            return DocumentType.PPTX
        if lower.endswith(EXTENSIONS_XLSX):
            return DocumentType.XLSX
        if lower.endswith(EXTENSIONS_CSV):
            return DocumentType.CSV
        return DocumentType.UNKNOWN

    def _get_output_filename(self, input_path: str, doc_type: DocumentType) -> Path:
        if doc_type == DocumentType.URL:
            parsed = urlparse(input_path)
            base = f"{parsed.netloc}_{parsed.path}".replace("/", "_").replace(".", "_")
            base = "".join(c for c in base if c.isalnum() or c == "_").strip("_") or "url_document"
        else:
            base = Path(input_path).stem
        return self.config.output_dir / f"{base}{OUTPUT_EXTENSION}"

    def _create_converter(self, doc_type: DocumentType) -> DocumentConverterType:
        """Wire PdfPipelineOptions into DocumentConverter when OCR is required (Docling best practice)."""
        if self.config.force_ocr:
            pdf_options = PdfPipelineOptions()
            pdf_options.do_ocr = True
            self.logger.info("OCR enabled (PdfPipelineOptions.do_ocr=True)")
            return DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
                }
            )
        return DocumentConverter()

    def _decrypt_pdf_to_temp(self, input_path: str, password: str) -> str:
        if not pypdf:
            raise ProcessorError("pypdf is required for encrypted PDFs. Install with: pip install pypdf")

        try:
            reader = pypdf.PdfReader(input_path)
        except OSError as exc:
            raise ProcessorError(f"Cannot open PDF: {exc}") from exc
        except Exception as exc:
            raise ProcessorError(f"Invalid or unreadable PDF: {exc}") from exc

        if not reader.decrypt(password):
            raise ProcessorError("Incorrect PDF password or decryption failed")

        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", prefix="decrypted_", delete=False)
        temp_path = tmp.name
        try:
            writer = pypdf.PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            writer.write(tmp)
            tmp.flush()
        except Exception:
            tmp.close()
            try:
                os.remove(temp_path)
            except OSError:
                pass
            raise
        tmp.close()

        self.logger.debug("Decrypted PDF written to temporary file: %s", temp_path)
        return temp_path

    def _prepare_pdf_input(self, input_path: str) -> tuple[str, Optional[str]]:
        """
        Return (path_to_convert, temp_path_or_none).
        temp_path must be removed by caller when conversion finishes.
        """
        if not os.path.isfile(input_path):
            raise ProcessorError(f"File not found: {input_path}")

        encrypted = _pdf_is_encrypted(input_path)
        if not encrypted:
            if self.config.password:
                self.logger.warning("Password was provided but PDF is not encrypted; ignoring password")
            return input_path, None

        self.logger.warning("Password-protected PDF: %s", input_path)
        if not self.config.password:
            raise ProcessorError("PDF is encrypted; provide --password / ProcessingConfig.password")

        temp = self._decrypt_pdf_to_temp(input_path, self.config.password)
        self.logger.info("Decrypted PDF for Docling pipeline")
        return temp, temp

    def process_document(self, input_path: str) -> Optional[Path]:
        self.logger.info("Processing: %s", input_path)

        doc_type = self._detect_document_type(input_path)
        self.logger.info("Document type: %s", doc_type.value)

        if doc_type == DocumentType.UNKNOWN:
            self.logger.error("Unknown document type: %s", input_path)
            return None

        temp_file: Optional[str] = None
        path_to_convert = input_path

        try:
            if doc_type == DocumentType.PDF and not input_path.startswith(URL_PROTOCOLS):
                path_to_convert, temp_file = self._prepare_pdf_input(input_path)

            output_path = self._get_output_filename(input_path, doc_type)
            converter = self._create_converter(doc_type)

            self.logger.info("Converting document...")
            result = converter.convert(path_to_convert)

            self.logger.info("Exporting to markdown: %s", output_path)
            markdown_content = result.document.export_to_markdown()

            try:
                output_path.write_text(markdown_content, encoding="utf-8")
            except OSError as exc:
                self.logger.error("Failed to write output %s: %s", output_path, exc)
                return None

            self.logger.info("%s Successfully saved: %s", SYMBOL_SUCCESS, output_path)
            return output_path

        except ProcessorError as exc:
            self.logger.error("%s", exc)
            return None
        except OSError as exc:
            self.logger.error("I/O error during conversion: %s", exc)
            if self.config.verbose:
                self.logger.exception("Details:")
            return None
        except Exception as exc:  # Docling may raise various conversion errors
            self.logger.error("Processing failed: %s", exc)
            if self.config.verbose:
                self.logger.exception("Details:")
            return None
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    self.logger.debug("Removed temporary decrypted file")
                except OSError as exc:
                    self.logger.warning("Could not remove temporary file %s: %s", temp_file, exc)

    def process_batch(self, input_paths: list[str]) -> dict[str, Optional[Path]]:
        results: dict[str, Optional[Path]] = {}
        total = len(input_paths)
        self.logger.info("Processing %d document(s)...", total)

        for idx, path in enumerate(input_paths, 1):
            self.logger.info("\n[%d/%d] Processing: %s", idx, total, path)
            results[path] = self.process_document(path)

        successful = sum(1 for v in results.values() if v is not None)
        self.logger.info(
            "\n%s\nProcessing complete: %d/%d successful\n%s",
            SEPARATOR,
            successful,
            total,
            SEPARATOR,
        )
        return results


def collect_files_from_directory(directory: Path, recursive: bool = False) -> list[str]:
    if not directory.is_dir():
        return []

    iterator = directory.rglob("*") if recursive else directory.glob("*")
    files = [
        str(p)
        for p in iterator
        if p.is_file() and p.suffix.lower() in ALL_EXTENSIONS
    ]
    return sorted(files)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert documents (PDF, DOCX, PPTX, XLSX, CSV, URL) to Markdown using Docling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python processor.py document.pdf
  python processor.py encrypted.pdf --password mypassword
  python processor.py file1.pdf file2.docx ./documents/
  python processor.py ./documents/ --recursive
  python processor.py https://example.com/document.pdf
  python processor.py document.pdf --output-dir ./converted
  python processor.py scanned.pdf --force-ocr --verbose
""",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Path(s) to document(s), directory, or URL(s) to process",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path(DEFAULT_OUTPUT_DIR),
        help=f"Output directory for markdown files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "-p",
        "--password",
        help="Password for encrypted PDFs",
    )
    parser.add_argument(
        "--force-ocr",
        action="store_true",
        help="Force OCR for PDF (PdfPipelineOptions.do_ocr)",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively collect files from directories",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging",
    )
    args = parser.parse_args()

    try:
        _ensure_docling_loaded()
    except ProcessorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    all_inputs: list[str] = []
    for raw in args.inputs:
        p = Path(raw)
        if p.is_dir():
            found = collect_files_from_directory(p, recursive=args.recursive)
            if found:
                all_inputs.extend(found)
            else:
                print(f"Warning: No supported files in directory: {raw}", file=sys.stderr)
        else:
            all_inputs.append(raw)

    if not all_inputs:
        print("Error: No valid files to process", file=sys.stderr)
        sys.exit(1)

    config = ProcessingConfig(
        output_dir=args.output_dir,
        password=args.password,
        force_ocr=args.force_ocr,
        verbose=args.verbose,
    )

    try:
        processor = DoclingProcessor(config)
    except ProcessorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    results = processor.process_batch(all_inputs)
    failed = sum(1 for v in results.values() if v is None)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
