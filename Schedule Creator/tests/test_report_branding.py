import app_path  # noqa: F401
import base64
import io
import unittest
import zipfile
from xml.etree import ElementTree as ET

from PIL import Image

import attendance_reports
import report_branding
from test_attendance_snapshot import example_payload


def image_url(format):
    output = io.BytesIO()
    Image.new("RGB", (80, 40), "#126789").save(output, format=format)
    return f'data:image/{format.lower()};base64,' + base64.b64encode(output.getvalue()).decode("ascii")


class ReportBrandingTests(unittest.TestCase):
    def test_snapshot_cover_embeds_all_formats_and_preserves_data(self):
        payload = example_payload()
        payload["logoDataUrl"] = ""
        original = attendance_reports.workbook(payload)
        payload.update(businessName="=Example & Business", logoDataUrl=image_url("PNG"),
                       supportingImages=[image_url("JPEG"), image_url("WEBP")])
        branded = attendance_reports.workbook(payload)
        with zipfile.ZipFile(io.BytesIO(original)) as before, zipfile.ZipFile(io.BytesIO(branded)) as after:
            for name in before.namelist():
                if name not in {"xl/workbook.xml", "xl/_rels/workbook.xml.rels", "[Content_Types].xml"}:
                    self.assertEqual(after.read(name), before.read(name), name)
            ns = {"s": report_branding.SHEET_NS}
            workbook = ET.fromstring(after.read("xl/workbook.xml"))
            self.assertEqual([sheet.get("name") for sheet in workbook.findall(".//s:sheet", ns)],
                             ["Business branding", "Summary", "Attendance"])
            cover = ET.fromstring(after.read("xl/worksheets/business-branding.xml"))
            self.assertEqual(cover.find(".//s:t", ns).text, "=Example & Business")
            self.assertEqual(cover.findall(".//s:f", ns), [])
            self.assertEqual(after.read("xl/media/business-branding-1.png"),
                             base64.b64decode(payload["logoDataUrl"].split(",")[1]))
            self.assertEqual(after.read("xl/media/business-branding-2.jpeg"),
                             base64.b64decode(payload["supportingImages"][0].split(",")[1]))
            with Image.open(io.BytesIO(after.read("xl/media/business-branding-3.png"))) as converted:
                self.assertEqual(converted.format, "PNG")
                self.assertEqual(converted.size, (80, 40))
            drawing = ET.fromstring(after.read("xl/drawings/business-branding.xml"))
            xdr = {"d": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"}
            self.assertEqual(len(drawing.findall("d:oneCellAnchor", xdr)), 3)
            for extent in drawing.findall("d:oneCellAnchor/d:ext", xdr):
                self.assertAlmostEqual(int(extent.get("cx")) / int(extent.get("cy")), 2)
            relationships = ET.fromstring(after.read("xl/drawings/_rels/business-branding.xml.rels"))
            self.assertEqual(len(relationships), 3)
            for relationship in relationships:
                self.assertIn("xl/" + relationship.get("Target").removeprefix("../"), after.namelist())

    def test_second_supporting_image_keeps_its_slot_and_no_images_keeps_original(self):
        payload = example_payload()
        payload["logoDataUrl"] = ""
        original = attendance_reports.workbook(payload)
        self.assertEqual(report_branding.workbook_cover(original, {}), original)
        self.assertEqual(report_branding.html_images({}), "")
        branding = {"supportingImages": ["", image_url("PNG")]}
        with zipfile.ZipFile(io.BytesIO(report_branding.workbook_cover(original, branding))) as archive:
            drawing = ET.fromstring(archive.read("xl/drawings/business-branding.xml"))
            ns = {"d": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"}
            self.assertEqual(drawing.find("d:oneCellAnchor/d:from/d:col", ns).text, "5")
            self.assertIn(b"Supporting image 2", archive.read("xl/drawings/business-branding.xml"))

    def test_invalid_image_fails_instead_of_producing_unbranded_workbook(self):
        payload = example_payload()
        payload["logoDataUrl"] = "data:image/png;base64,AAAA"
        with self.assertRaisesRegex(ValueError, "cannot be rendered"):
            attendance_reports.workbook(payload)


if __name__ == "__main__":
    unittest.main()
