"""Saved report branding and Excel cover sheets without altering report data."""

import base64
import io
import re
import zipfile
from html import escape
from xml.etree import ElementTree as ET

from PIL import Image

SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
TYPE_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
MAX_IMAGE_PIXELS = 40_000_000


def snapshot(s):
    branding = s.current_app_config()
    logo = s.validate_logo_data_url(branding.get("logoDataUrl", ""))
    if logo is None:
        raise ValueError("The saved business logo is invalid. Update branding before generating a report.")
    raw_images = branding.get("supportingImages", [])
    if not isinstance(raw_images, list) or len(raw_images) > 2:
        raise ValueError("Business supporting images are invalid. Update branding before generating a report.")
    images = [s.validate_logo_data_url(image) for image in raw_images]
    if any(image is None for image in images):
        raise ValueError("A business supporting image is invalid. Update branding before generating a report.")
    theme = branding.get("reportTheme", "light")
    return {
        "businessName": branding.get("businessName", "Workforce"),
        "teamName": branding.get("teamName", ""),
        "logoDataUrl": logo, "supportingImages": images,
        "reportTheme": theme if theme in ("light", "dark") else "light",
        "primaryColor": branding.get("primaryColor", "#176bd5"),
        "accentColor": branding.get("accentColor", "#079998"),
    }


def images(branding):
    result = []
    if branding.get("logoDataUrl"):
        result.append(("Business logo", branding["logoDataUrl"], 0, 5, 220, 110))
    for index, image in enumerate(branding.get("supportingImages", [])):
        if image:
            result.append((f"Supporting image {index + 1}", image, index * 5, 14, 280, 160))
    return result


def html_images(branding):
    saved_images = images(branding)
    if not saved_images:
        return ""
    return '<div class="report-branding">' + "".join(
        f'<img src="{escape(data_url, quote=True)}" alt="{escape(branding.get("businessName", "Business") + " " + label, quote=True)}">'
        for label, data_url, *_ in saved_images
    ) + "</div>"


def image_part(data_url):
    match = re.fullmatch(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)", data_url)
    if not match:
        raise ValueError("A saved report image is invalid. Update business branding.")
    try:
        data = base64.b64decode(match[2], validate=True)
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            if width * height > MAX_IMAGE_PIXELS:
                raise ValueError("A saved report image is too large to render. Use a smaller image.")
            if image.format != {"png": "PNG", "jpeg": "JPEG", "webp": "WEBP"}[match[1]]:
                raise ValueError("A saved report image does not match its declared format.")
            extension = match[1]
            if extension == "webp":
                output = io.BytesIO()
                image.thumbnail((1024, 1024))
                image.convert("RGBA").save(output, format="PNG")
                data, extension = output.getvalue(), "png"
                width, height = image.size
    except (OSError, Image.DecompressionBombError) as error:
        raise ValueError("A saved report image cannot be rendered. Update business branding.") from error
    return data, extension, width, height


def workbook_cover(content: bytes, branding: dict) -> bytes:
    saved_images = images(branding)
    if not saved_images:
        return content

    def safe(value):
        return escape("".join(char for char in str(value) if char in "\t\n\r" or ord(char) >= 32))

    with zipfile.ZipFile(io.BytesIO(content)) as source:
        files = {name: source.read(name) for name in source.namelist()}
    workbook = ET.fromstring(files["xl/workbook.xml"])
    sheets = workbook.find(f"{{{SHEET_NS}}}sheets")
    if sheets is None or not len(sheets):
        raise ValueError("The report workbook has no data sheets.")
    sheet_id = max(int(sheet.get("sheetId")) for sheet in sheets) + 1
    names = {sheet.get("name") for sheet in sheets}
    name = "Business branding"
    suffix = 2
    while name in names:
        name = f"Business branding {suffix}"
        suffix += 1
    relationship_id = f"branding{sheet_id}"
    sheets.insert(0, ET.Element(f"{{{SHEET_NS}}}sheet", {
        "name": name, "sheetId": str(sheet_id), f"{{{OFFICE_NS}}}id": relationship_id,
    }))
    views = workbook.find(f"{{{SHEET_NS}}}bookViews")
    if views is not None:
        for view in views:
            view.set("activeTab", "0")
            view.set("firstSheet", "0")
    relationships = ET.fromstring(files["xl/_rels/workbook.xml.rels"])
    ET.SubElement(relationships, f"{{{REL_NS}}}Relationship", {
        "Id": relationship_id, "Type": OFFICE_NS + "/worksheet", "Target": "worksheets/business-branding.xml",
    })
    types = ET.fromstring(files["[Content_Types].xml"])
    for part, content_type in (
        ("/xl/worksheets/business-branding.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"),
        ("/xl/drawings/business-branding.xml", "application/vnd.openxmlformats-officedocument.drawing+xml"),
    ):
        ET.SubElement(types, f"{{{TYPE_NS}}}Override", {"PartName": part, "ContentType": content_type})
    anchors, image_relationships = [], []
    for index, (label, data_url, column, row, max_width, max_height) in enumerate(saved_images, 1):
        data, extension, width, height = image_part(data_url)
        scale = min(max_width / width, max_height / height)
        cx, cy = round(width * scale * 9525), round(height * scale * 9525)
        files[f"xl/media/business-branding-{index}.{extension}"] = data
        if not any(item.get("Extension") == extension for item in types):
            ET.SubElement(types, f"{{{TYPE_NS}}}Default", {"Extension": extension, "ContentType": f"image/{extension}"})
        anchors.append(
            f'<xdr:oneCellAnchor><xdr:from><xdr:col>{column}</xdr:col><xdr:colOff>0</xdr:colOff>'
            f'<xdr:row>{row}</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from><xdr:ext cx="{cx}" cy="{cy}"/>'
            f'<xdr:pic><xdr:nvPicPr><xdr:cNvPr id="{index}" name="{escape(label)}"/><xdr:cNvPicPr/></xdr:nvPicPr>'
            f'<xdr:blipFill><a:blip r:embed="rId{index}"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill>'
            f'<xdr:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr></xdr:pic><xdr:clientData/></xdr:oneCellAnchor>'
        )
        image_relationships.append(
            f'<Relationship Id="rId{index}" Type="{OFFICE_NS}/image" Target="../media/business-branding-{index}.{extension}"/>'
        )
    rows = "".join(
        f'<row r="{index}"><c r="A{index}" t="inlineStr"><is><t>{safe(value)}</t></is></c></row>'
        for index, value in enumerate((branding.get("businessName", "Business"), branding.get("teamName", ""), "Report branding"), 1)
    )
    files["xl/worksheets/business-branding.xml"] = (
        f'<worksheet xmlns="{SHEET_NS}" xmlns:r="{OFFICE_NS}"><cols><col min="1" max="10" width="12" customWidth="1"/></cols>'
        f'<sheetData>{rows}</sheetData><pageSetup orientation="landscape" paperSize="9" fitToWidth="1" fitToHeight="1"/>'
        '<drawing r:id="rId1"/></worksheet>'
    ).encode()
    files["xl/worksheets/_rels/business-branding.xml.rels"] = (
        f'<Relationships xmlns="{REL_NS}"><Relationship Id="rId1" Type="{OFFICE_NS}/drawing" Target="../drawings/business-branding.xml"/></Relationships>'
    ).encode()
    files["xl/drawings/business-branding.xml"] = (
        f'<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" '
        f'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="{OFFICE_NS}">{"".join(anchors)}</xdr:wsDr>'
    ).encode()
    files["xl/drawings/_rels/business-branding.xml.rels"] = (
        f'<Relationships xmlns="{REL_NS}">{"".join(image_relationships)}</Relationships>'
    ).encode()
    files["xl/workbook.xml"] = ET.tostring(workbook, encoding="utf-8", xml_declaration=True)
    files["xl/_rels/workbook.xml.rels"] = ET.tostring(relationships, encoding="utf-8", xml_declaration=True)
    files["[Content_Types].xml"] = ET.tostring(types, encoding="utf-8", xml_declaration=True)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, data in files.items():
            archive.writestr(path, data)
    return output.getvalue()
