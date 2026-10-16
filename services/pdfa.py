"""Finalize new diplomas after visual stamping and before hashing/signing.

No fallback to ordinary PDF: a missing tool or failed validation aborts issuance.
This module deliberately uses only the Python standard library.
"""

import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


class PdfaError(RuntimeError):
    pass


def _tool(variable, default):
    executable = shutil.which(os.environ.get(variable, default))
    if not executable:
        raise PdfaError(f"{variable}: executable unavailable")
    return executable


def _run(command):
    try:
        result = subprocess.run(command, capture_output=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PdfaError("PDF/A tool unavailable or timed out") from exc
    if result.returncode != 0:
        raise PdfaError("PDF/A tool failed")
    return result.stdout


def validate_pdfa(path):
    """Return independent veraPDF report only for a single compliant 2b PDF."""
    report = _run([
        _tool("VERAPDF_BIN", "verapdf"), "--format", "xml",
        "--flavour", "2b", str(Path(path).resolve()),
    ])
    try:
        root = ET.fromstring(report)
        validations = [node for node in root.iter()
                       if node.tag.split("}")[-1] == "validationReport"]
        summaries = [node for node in root.iter()
                     if node.tag.split("}")[-1] == "batchSummary"]
        if len(validations) != 1 or validations[0].get("isCompliant") != "true":
            raise PdfaError("veraPDF rejected PDF/A-2b")
        if validations[0].get("profileName") != "PDF/A-2b validation profile":
            raise PdfaError("veraPDF used an unexpected validation profile")
        if len(summaries) != 1 or summaries[0].get("totalJobs") != "1":
            raise PdfaError("veraPDF returned an incomplete report")
        for field in ("failedToParse", "encrypted", "outOfMemory", "veraExceptions"):
            if summaries[0].get(field) != "0":
                raise PdfaError("veraPDF failed to process the document")
    except ET.ParseError as exc:
        raise PdfaError("veraPDF returned invalid XML") from exc
    return report


def finalize_pdfa(source):
    """Convert to PDF/A-2b and validate; return immutable bytes plus XML evidence.

    Never rewrites source. Temporary files use a private per-request directory.
    ICC path is copied to a fixed safe name rather than interpolated in PostScript.
    """
    gs = _tool("GHOSTSCRIPT_BIN", "gs")
    icc = Path(os.environ.get("PDFA_ICC_PROFILE", "/usr/share/color/icc/ghostscript/srgb.icc"))
    if not icc.is_file():
        raise PdfaError("PDFA_ICC_PROFILE: sRGB profile unavailable")
    with tempfile.TemporaryDirectory(prefix="diploma-pdfa-") as directory:
        work = Path(directory)
        profile = work / "srgb.icc"
        shutil.copyfile(icc, profile)
        input_pdf = work / "input.pdf"
        shutil.copyfile(source, input_pdf)
        output = work / "final.pdf"
        definition = work / "output-intent.ps"
        definition.write_text("""%!
[/_objdef {icc_PDFA} /type /stream /OBJ pdfmark
[{icc_PDFA} << /N 3 >> /PUT pdfmark
[{icc_PDFA} (""" + str(profile) + """) (r) file /PUT pdfmark
[/_objdef {OutputIntent_PDFA} /type /dict /OBJ pdfmark
[{OutputIntent_PDFA} << /Type /OutputIntent /S /GTS_PDFA1
/DestOutputProfile {icc_PDFA} /OutputConditionIdentifier (sRGB) >> /PUT pdfmark
[{Catalog} << /OutputIntents [{OutputIntent_PDFA}] >> /PUT pdfmark
""", encoding="ascii")
        _run([
            gs, "-dSAFER", "-dBATCH", "-dNOPAUSE", "-dPDFSTOPONERROR",
            "-sDEVICE=pdfwrite", "-dPDFA=2", "-dCompatibilityLevel=1.7",
            "-dPDFACompatibilityPolicy=2", "-sColorConversionStrategy=RGB",
            "-sBlendConversionStrategy=Managed", "-dEmbedAllFonts=true",
            "-dSubsetFonts=true", "-dAutoRotatePages=/None",
            "-dDownsampleColorImages=false", "-dDownsampleGrayImages=false",
            "-dDownsampleMonoImages=false", "--permit-file-read=" + str(profile),
            "-sOutputFile=" + str(output), str(definition), str(input_pdf),
        ])
        report = validate_pdfa(output)
        return output.read_bytes(), report
