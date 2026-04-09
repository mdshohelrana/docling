"""Convert documents to Markdown using Docling (CLI and programmatic API)."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
import time

from tqdm import tqdm
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.base_models import ConversionStatus, InputFormat
    from docling.datamodel.pipeline_options import ThreadedPdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.pipeline.threaded_standard_pdf_pipeline import ThreadedStandardPdfPipeline
except ImportError as _e:  # pragma: no cover
    AcceleratorDevice = None  # type: ignore[misc, assignment]
    AcceleratorOptions = None  # type: ignore[misc, assignment]
    ConversionStatus = None  # type: ignore[misc, assignment]
    DocumentConverter = None  # type: ignore[misc, assignment]
    InputFormat = None  # type: ignore[misc, assignment]
    PdfFormatOption = None  # type: ignore[misc, assignment]
    ThreadedPdfPipelineOptions = None  # type: ignore[misc, assignment]
    ThreadedStandardPdfPipeline = None  # type: ignore[misc, assignment]
    _DOCLING_IMPORT_ERROR = _e
else:
    _DOCLING_IMPORT_ERROR = None

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
    pass


@dataclass
class ProcessingConfig:
    output_dir: Path = field(default_factory=lambda: Path(DEFAULT_OUTPUT_DIR))
    password: Optional[str] = None
    force_ocr: bool = False
    use_cuda: bool = False


def _ensure_docling_loaded() -> None:
    if _DOCLING_IMPORT_ERROR is not None:
        raise ProcessorError(
            "Docling is not installed. Install with: pip install docling"
        ) from _DOCLING_IMPORT_ERROR


def _pdf_is_encrypted(path: str) -> bool:
    if not pypdf:
        return False
    with open(path, "rb") as f:
        return bool(pypdf.PdfReader(f).is_encrypted)


def _decrypt_pdf_to_temp(input_path: str, password: str) -> str:
    if not pypdf:
        raise ProcessorError("Install pypdf for encrypted PDFs: pip install pypdf")
    reader = pypdf.PdfReader(input_path)
    if not reader.decrypt(password):
        raise ProcessorError("Incorrect PDF password or decryption failed")
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", prefix="decrypted_", delete=False)
    temp_path = tmp.name
    writer = pypdf.PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    try:
        writer.write(tmp)
        tmp.flush()
    finally:
        tmp.close()
    return temp_path


def _accelerator_device(cfg: ProcessingConfig) -> "AcceleratorDevice":
    if cfg.use_cuda:
        return AcceleratorDevice.CUDA
    return AcceleratorDevice.CPU


class DoclingProcessor:
    def __init__(self, config: Optional[ProcessingConfig] = None) -> None:
        _ensure_docling_loaded()
        self.config = config or ProcessingConfig()
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

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

    def _create_threaded_pdf_converter(self) -> DocumentConverter:
        pipeline_options = ThreadedPdfPipelineOptions(
            accelerator_options=AcceleratorOptions(device=_accelerator_device(self.config)),
            ocr_batch_size=4,
            layout_batch_size=64,
            table_batch_size=4,
        )
        pipeline_options.do_ocr = self.config.force_ocr
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=ThreadedStandardPdfPipeline,
                    pipeline_options=pipeline_options,
                )
            }
        )

    def _prepare_local_pdf(self, input_path: str) -> tuple[str, Optional[str]]:
        if not os.path.isfile(input_path):
            raise ProcessorError(f"File not found: {input_path}")
        if not _pdf_is_encrypted(input_path):
            return input_path, None
        if not self.config.password:
            raise ProcessorError("PDF is encrypted; set password in ProcessingConfig")
        temp_path = _decrypt_pdf_to_temp(input_path, self.config.password)
        return temp_path, temp_path

    def process_document(self, input_path: str) -> Path:
        doc_type = self._detect_document_type(input_path)
        if doc_type == DocumentType.UNKNOWN:
            raise ProcessorError(f"Unknown document type: {input_path}")

        temp_path: Optional[str] = None
        path_to_convert = input_path

        if doc_type == DocumentType.PDF:
            path_to_convert, temp_path = self._prepare_local_pdf(input_path)

        output_path = self._get_output_filename(input_path, doc_type)

        try:
            if doc_type == DocumentType.PDF:
                doc_converter = self._create_threaded_pdf_converter()
                doc_converter.initialize_pipeline(InputFormat.PDF)
            else:
                doc_converter = DocumentConverter()

            conv_result = doc_converter.convert(path_to_convert)
            if conv_result.status != ConversionStatus.SUCCESS:
                raise ProcessorError(f"Conversion failed: {conv_result.status}")

            output_path.write_text(conv_result.document.export_to_markdown(), encoding="utf-8")
            return output_path
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    def process_batch(self, input_paths: list[str]) -> dict[str, Path]:
        return {p: self.process_document(p) for p in input_paths}


def collect_files_from_directory(directory: Path, recursive: bool = False) -> list[str]:
    if not directory.is_dir():
        return []
    iterator = directory.rglob("*") if recursive else directory.glob("*")
    return sorted(
        str(p)
        for p in iterator
        if p.is_file() and p.suffix.lower() in ALL_EXTENSIONS
    )


def main() -> None:
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    logging.getLogger("docling").setLevel(logging.ERROR)

    parser = argparse.ArgumentParser(
        description="Convert documents to Markdown with Docling (threaded PDF pipeline for local PDFs).",
    )
    parser.add_argument("inputs", nargs="+", help="Files, directories, or URLs")
    parser.add_argument("-o", "--output-dir", type=Path, default=Path(DEFAULT_OUTPUT_DIR))
    parser.add_argument("-p", "--password", help="Password for encrypted PDFs")
    parser.add_argument("--force-ocr", action="store_true", help="Enable OCR on PDF pipeline")
    parser.add_argument("--cuda", action="store_true", help="Use AcceleratorDevice.CUDA for threaded PDF pipeline")
    parser.add_argument("-r", "--recursive", action="store_true")
    args = parser.parse_args()

    _ensure_docling_loaded()

    all_inputs: list[str] = []
    for raw in args.inputs:
        p = Path(raw)
        if p.is_dir():
            found = collect_files_from_directory(p, recursive=args.recursive)
            if not found:
                print(f"No supported files in: {raw}", file=sys.stderr)
                sys.exit(1)
            all_inputs.extend(found)
        else:
            all_inputs.append(raw)

    if not all_inputs:
        print("No inputs to process.", file=sys.stderr)
        sys.exit(1)

    cfg = ProcessingConfig(
        output_dir=args.output_dir,
        password=args.password,
        force_ocr=args.force_ocr,
        use_cuda=args.cuda,
    )
    proc = DoclingProcessor(cfg)
    total_start = time.perf_counter()
    with tqdm(all_inputs, desc="Processing", unit="file") as pbar:
        for path in pbar:
            pbar.set_postfix_str(Path(path).name, refresh=False)
            tqdm.write(str(proc.process_document(path)), file=sys.stdout)
    print(
        f"Total processing time: {time.perf_counter() - total_start:.2f} seconds",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
