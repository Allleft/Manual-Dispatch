from io import BytesIO

from datetime import datetime
from decimal import Decimal, InvalidOperation
import math
import re
import unicodedata

from openpyxl import Workbook
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
from openpyxl.worksheet.page import PageMargins
from openpyxl.worksheet.pagebreak import Break
from backend.services.manual_dispatch.delivery_run_sheet_ordering import delivery_run_sheet_driver_trip_key
from backend.services.manual_dispatch.attache_carton_packaging import cartonized_product_weight_kg


DAILY_RUN_SHEET_HEADERS = [
    "Sequence",
    "Customer Name",
    "Suburb",
    "Invoice #",
    "PRODUCT",
    "KG'S",
    "Pallets",
    "COD",
    "CQ",
    "Time In",
    "Time Out",
    "PRINT NAME",
    "SIGNATURE",
    "RETND",
]
HANDWRITING_ROW_COUNT = 2
PRODUCT_SUMMARY_HEADING = "PRODUCT QUANTITY SUMMARY (EXCLUDING PALLETS)"
PRODUCT_SUMMARY_FONT_SIZE = 12
PRODUCT_SUMMARY_LINE_HEIGHT = PRODUCT_SUMMARY_FONT_SIZE * 1.4
BODY_FONT_SIZE = 8.5
PRODUCT_FONT_SIZE = 8.0
PRODUCT_QUANTITY_COLOR = "C00000"
MIN_BODY_ROW_HEIGHT = 21.95
BODY_LINE_HEIGHT = 10.5
PRODUCT_LINE_HEIGHT = PRODUCT_FONT_SIZE * 1.4
BODY_ROW_PADDING = 4
EXCEL_MAX_ROW_HEIGHT = 409.5
COLUMN_WIDTHS = {
    "A": 3.855,
    "B": 27.57,
    "C": 15,
    "D": 12,
    "E": 20,
    "F": 5.57,
    "G": 6.855,
    "H": 5.855,
    "I": 3,
    "J": 8,
    "K": 8,
    "L": 12.57,
    "M": 17.285,
    "N": 7.71,
}
_INVALID_SHEET_NAME_CHARACTERS = re.compile(r"[\\/*?:\[\]]")
_PRODUCT_CODE_KG_SUFFIX = re.compile(r"([0-9]+(?:\.[0-9]+)?)KG$", re.IGNORECASE)
_PACKAGE_UNIT_BAG_WEIGHT = re.compile(
    r"BAG\s*([0-9]+(?:\.[0-9]+)?)",
    re.IGNORECASE,
)


def build_delivery_run_sheet_excel(run_sheet):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = (
        _unique_sheet_name(run_sheet.driver_name_snapshot, set(), run_sheet.trip_no)
        if run_sheet.trip_no is not None else "Daily Run Sheet"
    )
    _configure_print_layout(worksheet)
    _write_daily_run_sheet_form(worksheet, run_sheet, run_sheet.delivery_date)
    return _save(workbook)


def build_delivery_run_sheets_excel(run_sheets, delivery_date):
    if not run_sheets:
        raise ValueError(
            "No Generated or Saved Delivery Run Sheets are available for this Delivery Date."
        )

    workbook = Workbook()
    workbook.remove(workbook.active)
    used_sheet_names = set()
    for run_sheet in sorted(run_sheets, key=delivery_run_sheet_driver_trip_key):
        worksheet = workbook.create_sheet(
            _unique_sheet_name(run_sheet.driver_name_snapshot, used_sheet_names, run_sheet.trip_no)
        )
        _configure_print_layout(worksheet)
        _write_daily_run_sheet_form(worksheet, run_sheet, delivery_date)
    return _save(workbook)


def _configure_print_layout(worksheet):
    worksheet.page_setup.orientation = "landscape"
    worksheet.page_setup.paperSize = worksheet.PAPERSIZE_A4
    worksheet.page_setup.fitToWidth = 1
    worksheet.page_setup.fitToHeight = 0
    worksheet.sheet_properties.pageSetUpPr.fitToPage = True
    worksheet.page_margins = PageMargins(
        left=0.118,
        right=0.197,
        top=0.394,
        bottom=0.157,
        header=0.315,
        footer=0.315,
    )


def _write_daily_run_sheet_form(worksheet, run_sheet, delivery_date):
    _apply_column_widths(worksheet)
    _apply_row_heights(worksheet)
    worksheet.sheet_view.showGridLines = False
    worksheet.print_options.horizontalCentered = False
    worksheet.print_title_rows = "7:8"

    worksheet["A1"] = "DAILY RUN SHEET"
    worksheet["C1"] = f"DATE  {_display_date(delivery_date)}"
    worksheet["F1"] = f"DRIVER: {run_sheet.driver_name_snapshot or ''}"
    worksheet["L1"] = f"REGO #: {_rego_snapshot_display(run_sheet)}"
    for coordinate, font_size in (("A1", 16), ("C1", 11), ("F1", 11), ("L1", 14)):
        worksheet[coordinate].font = Font(bold=True, size=font_size)
        worksheet[coordinate].alignment = Alignment(
            vertical="center",
            horizontal="center" if coordinate == "L1" else "left",
            wrap_text=False,
            shrink_to_fit=False,
        )
    highlight_fill = PatternFill(fill_type="solid", fgColor="C6E0B4")
    worksheet["F1"].fill = highlight_fill
    worksheet["L1"].fill = highlight_fill

    if run_sheet.trip_no is not None:
        worksheet["F2"] = f"TRIP: TRIP {1 if run_sheet.trip_no == 'trip1' else 2}"
        worksheet["F2"].font = Font(bold=True, size=11)
        worksheet["F2"].alignment = Alignment(vertical="center")

    worksheet["B3"] = "START TIME: ____________________________________"
    worksheet.merge_cells("B5:E5")
    worksheet["B5"] = "TIME LOADING STARTED(TO BE FILLED IN BY STOREMAN)___________"
    worksheet.merge_cells("F5:N5")
    worksheet["F5"] = "TIME LOADING COMPLETED(TO BE FILLED IN BY STOREMAN)_____________"
    for coordinate, font_size in (("B3", 16), ("B5", 12), ("F5", 12)):
        worksheet[coordinate].font = Font(bold=True, size=font_size)
        worksheet[coordinate].alignment = Alignment(vertical="center", wrap_text=False)

    worksheet["N6"] = "NO. #"
    worksheet["J7"] = "Time"
    worksheet["K7"] = "Time"
    worksheet["M7"] = "Comments"
    worksheet["N7"] = "PALLETS"
    for coordinate in ("J7", "K7", "N6", "N7"):
        worksheet[coordinate].font = Font(bold=True, size=11)
        worksheet[coordinate].alignment = Alignment(horizontal="center", vertical="center")
    worksheet["M7"].font = Font(size=11)
    worksheet["M7"].alignment = Alignment(horizontal="center", vertical="center")
    returned_pallets_fill = PatternFill(fill_type="solid", fgColor="FFFF00")
    for coordinate in ("N6", "N7"):
        worksheet[coordinate].fill = returned_pallets_fill

    thin = Side(style="thin", color="000000")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_row = 8
    for column_index, header in enumerate(DAILY_RUN_SHEET_HEADERS, start=1):
        cell = worksheet.cell(row=header_row, column=column_index, value=header)
        cell.font = Font(bold=column_index != 5, size=9)
        cell.border = border
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    worksheet["N8"].fill = returned_pallets_fill
    worksheet.row_dimensions[header_row].height = 21

    snapshot_rows = _ordered_snapshot_rows(run_sheet)
    summary_rows = _product_quantity_summary_rows(snapshot_rows)
    row_index = header_row + 1
    for row_no, order in enumerate(snapshot_rows, start=1):
        row_index += _write_order_row(worksheet, row_index, row_no, order, border)
    handwriting_start = row_index
    for row_no in range(len(snapshot_rows) + 1, len(snapshot_rows) + HANDWRITING_ROW_COUNT + 1):
        _write_empty_row(worksheet, row_index, row_no, border)
        row_index += 1

    finish = worksheet.cell(row=row_index + 1, column=2, value="FINISH TIME:____________________________________")
    finish.font = Font(bold=True, size=16)
    finish.alignment = Alignment(vertical="center")
    worksheet.row_dimensions[row_index + 1].height = 21
    worksheet.row_dimensions[row_index].height = 15
    handwriting_layout = _PrintLayout(worksheet, handwriting_start)
    handwriting_height = sum(_print_row_height(worksheet, row) for row in range(handwriting_start, finish.row + 1))
    if handwriting_height > handwriting_layout.remaining:
        handwriting_layout.new_page(handwriting_start)
    summary_start = row_index + 3
    print_end = finish.row
    if summary_rows:
        worksheet.row_dimensions[finish.row + 1].height = 15
        print_end = _write_product_quantity_summary(worksheet, summary_start, summary_rows, border)
    worksheet.print_area = f"A1:N{print_end}"


def _print_row_height(worksheet, row):
    dimension = worksheet.row_dimensions[row]
    if dimension.hidden:
        return 0
    height = dimension.height or worksheet.sheet_format.defaultRowHeight or 15
    return math.ceil(height * 5 - 1e-9) / 5


class _PrintLayout:
    def __init__(self, worksheet, next_row):
        self.worksheet = worksheet
        # Calibri 11 column metrics include padding/gridlines. Fit-to-width uses
        # a whole percentage; leave room for printer/row-height rounding.
        width = sum((worksheet.column_dimensions[column].width * 7 + 6) * 0.75
                    for column in COLUMN_WIDTHS)
        margins = worksheet.page_margins
        scale = min(1, math.floor((297 / 25.4 * 72 - (margins.left + margins.right) * 72) / width * 100) / 100)
        self.page_height = (210 / 25.4 * 72 - (max(margins.top, 0.2) + max(margins.bottom, 0.2)) * 72) / scale - 1.5
        # Native Excel reserves an additional print gap around repeated titles.
        self.repeated_height = sum(_print_row_height(worksheet, row) for row in (7, 8)) + 4
        self.used = 0
        breaks = {item.id + 1 for item in worksheet.row_breaks.brk}
        for row in range(1, next_row):
            height = _print_row_height(worksheet, row)
            if row in breaks or height > self.remaining:
                self.used = self.repeated_height
            self.used += height

    @property
    def remaining(self):
        return self.page_height - self.used

    @property
    def fresh_space(self):
        return self.page_height - self.repeated_height

    def new_page(self, row):
        self.worksheet.row_breaks.append(Break(id=row - 1))
        self.used = self.repeated_height

    def consume(self, height):
        self.used += math.ceil(height * 5 - 1e-9) / 5


def _ordered_snapshot_rows(run_sheet):
    return [
        order
        for trip in (run_sheet.trips or [])
        for order in (trip.orders or [])
    ]


def _bag_count(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        count = Decimal(str(value))
    except InvalidOperation:
        return None
    return int(count) if count.is_finite() and count >= 0 and count == count.to_integral_value() else None


def _bag_type(unit):
    unit = str(unit or "").strip().upper()
    if unit in {"BAG", "BAGS"}:
        return "Bag"
    match = _PACKAGE_UNIT_BAG_WEIGHT.fullmatch(unit)
    if match and Decimal(match.group(1)) > 0:
        return f"{Decimal(match.group(1)).normalize():f}kg Bag"
    return None


def _loose_bag_summary(snapshot_rows):
    products = {}
    total = unallocated = 0
    for order in snapshot_rows:
        loose = _bag_count(order.loose_bags_quantity_snapshot)
        if loose is None:
            raise ValueError("Loose bag snapshot quantity must be a non-negative whole number.")
        total += loose
        if not loose:
            continue
        lines = order.product_lines_snapshot or []
        allocation = []
        if order.pallet_quantity_snapshot == 0 and lines:
            for line in lines:
                unit = str(line.package_unit or "").strip().upper()
                bag_type = _bag_type(unit)
                if not bag_type:
                    # An explicit non-bag package cannot contribute bags. Unknown
                    # packaging may hide bags, so the whole order stays unallocated.
                    if (str(line.unit or "").strip().upper() not in {"BAG", "BAGS"}
                            and re.fullmatch(r"CTNS?|CARTONS?|PKT\d*|PACKETS?|EA|EACH|ROLLS?|UNITS?", unit)):
                        continue
                    break
                count = _bag_count(line.package_quantity)
                name = str(line.product_name or "").strip()
                code = str(line.product_code or "").strip()
                if count is None or not (name or code):
                    break
                allocation.append(((name or code, code, bag_type), count))
            else:
                if sum(count for _, count in allocation) == loose:
                    for key, count in allocation:
                        if count:
                            products[key] = products.get(key, 0) + count
                    continue
        unallocated += loose
    return products, total - unallocated, unallocated, total


def _summary_package_type(unit):
    unit = str(unit or "").strip().upper()
    if unit in {"BAG", "BAGS"}:
        return "BAG"
    bag_type = _bag_type(unit)
    if bag_type:
        return bag_type
    # Weight/volume/length measurements cannot establish a package count.
    measurements = {
        "KG", "KGS", "G", "GRAM", "GRAMS", "MG", "T", "TON", "TONNE", "TONNES",
        "LB", "LBS", "OZ", "L", "LT", "LTR", "LITRE", "LITRES", "ML",
        "M", "CM", "MM", "M2", "M3", "SQM", "CBM",
    }
    if (unit in measurements or unit in {"UNKNOWN", "N/A", "NA"}
            or unit.startswith("BAG") or len(unit) > 20
            or not re.fullmatch(r"[A-Z][A-Z0-9./_-]*", unit)):
        return None
    return unit


def _summary_package(line):
    quantity = getattr(line, "package_quantity", None)
    unit = str(getattr(line, "package_unit", "") or "").strip()
    # Fall back only when both optional package fields are absent.
    if quantity in (None, "") and not unit:
        quantity = getattr(line, "quantity", None)
        unit = getattr(line, "unit", None)
    count = _bag_count(quantity)
    package_type = _summary_package_type(unit)
    return (count, package_type) if count is not None and package_type else None


def _product_quantity_summary(snapshot_rows):
    products = {}
    names = {}
    for order in snapshot_rows:
        pallets = getattr(order, "pallet_quantity_snapshot", None)
        if not isinstance(pallets, int) or isinstance(pallets, bool) or pallets < 0:
            raise ValueError("Pallet snapshot quantity must be a non-negative integer.")
        if pallets > 0:
            continue
        for line in getattr(order, "product_lines_snapshot", None) or []:
            name = str(getattr(line, "product_name", "") or "").strip()
            code = str(getattr(line, "product_code", "") or "").strip().upper()
            package = _summary_package(line)
            if not (name or code) or package is None:
                continue
            count, package_type = package
            # A frozen SKU identifies the product even when its name is absent.
            identity = ("code", code) if code else ("name", name)
            key = (identity, code, package_type)
            products[key] = products.get(key, 0) + count
            names.setdefault(identity, set())
            if name:
                names[identity].add(name)
    result = {}
    for (identity, code, package_type), count in products.items():
        name = min(names[identity], key=lambda value: (value.casefold(), value)) if names[identity] else code
        result[(name, code, package_type)] = count
    return dict(sorted(result.items(), key=lambda item: (
        item[0][0].casefold(), item[0][0], item[0][1], item[0][2],
    )))


def _summary_quantity_format(package_type, quantity):
    if package_type.endswith("kg Bag"):
        unit = "Bag" if quantity == 1 else "Bags"
    elif package_type == "CARTON":
        unit = "Carton" if quantity == 1 else "Cartons"
    else:
        unit = package_type
    return '#,##0" ' + unit + '"', unit


def _product_quantity_summary_rows(snapshot_rows):
    products = _product_quantity_summary(snapshot_rows)
    if not products:
        return []
    rows = [(PRODUCT_SUMMARY_HEADING, None, None, 21, "General"),
            ("PRODUCT", "PACKAGE TYPE", "QTY", 21, "General")]
    product_width = sum(COLUMN_WIDTHS[column] for column in "ABCDE")
    package_width = sum(COLUMN_WIDTHS[column] for column in "FGHI")
    quantity_width = sum(COLUMN_WIDTHS[column] for column in "JKLMN")
    for (name, code, package_type), quantity in products.items():
        ambiguous = len({key[1] for key in products if key[0] == name and key[2] == package_type}) > 1
        label = f"{name} ({code or 'code not recorded'})" if ambiguous else name
        number_format, unit = _summary_quantity_format(package_type, quantity)
        # Excel numeric cells retain only 15 significant decimal digits.
        value = quantity if quantity < 10 ** 15 else f"{quantity:,} {unit}"
        lines = _wrapped_lines(label, product_width, PRODUCT_SUMMARY_FONT_SIZE)
        for offset in range(0, len(lines), 24):
            fragment = lines[offset:offset + 24]
            line_count = max(
                len(fragment),
                _wrapped_line_count(package_type if not offset else "continued", package_width, PRODUCT_SUMMARY_FONT_SIZE),
                _wrapped_line_count(f"{quantity:,} {unit}" if not offset else "", quantity_width, PRODUCT_SUMMARY_FONT_SIZE),
            )
            rows.append(("".join(fragment), package_type if not offset else "continued",
                         value if not offset else None, max(21, line_count * PRODUCT_SUMMARY_LINE_HEIGHT + 6), number_format))
    return rows


def _write_product_quantity_summary(worksheet, start, rows, border):
    layout = _PrintLayout(worksheet, start)
    headers = rows[:2]
    header_height = sum(row[3] for row in headers)
    groups = []
    for item in rows[2:]:
        if item[1] != "continued":
            groups.append([])
        groups[-1].append(item)
    total_height = sum(item[3] for item in rows)
    first_group = sum(item[3] for item in groups[0])
    # Keep the whole summary when it fits a fresh page; otherwise keep the
    # heading/columns with at least the first printable product fragment.
    first_height = first_group if first_group <= layout.fresh_space - header_height else groups[0][0][3]
    required = total_height if total_height <= layout.fresh_space else header_height + first_height
    if required > layout.remaining:
        layout.new_page(start)
    cursor = start

    def write(item):
        nonlocal cursor
        _write_product_quantity_summary_row(worksheet, cursor, item, border)
        layout.consume(item[3])
        cursor += 1

    def next_page():
        layout.new_page(cursor)
        for header in headers:
            write(header)

    for header in headers:
        write(header)
    for group in groups:
        group_height = sum(item[3] for item in group)
        if group_height <= layout.fresh_space - header_height and group_height > layout.remaining:
            next_page()
        for item in group:
            if item[3] > layout.remaining:
                next_page()
            write(item)
    return cursor - 1


def _write_product_quantity_summary_row(worksheet, row, item, border):
    product, package_type, quantity, height, number_format = item
    title = package_type is None
    heading = title or package_type == "PACKAGE TYPE"
    ranges = ((1, 14, product),) if title else (
        (1, 5, product), (6, 9, package_type), (10, 14, quantity)
    )
    for first, last, value in ranges:
        worksheet.merge_cells(start_row=row, start_column=first, end_row=row, end_column=last)
        font = Font(size=10 if title else PRODUCT_SUMMARY_FONT_SIZE, bold=heading,
                    color=PRODUCT_QUANTITY_COLOR if not heading and first == 10 else "000000")
        for column in range(first, last + 1):
            worksheet.cell(row, column).border = border
            if not title:
                worksheet.cell(row, column).font = font
        cell = worksheet.cell(row, first, value)
        if isinstance(value, str):
            cell.data_type = "s"
        cell.font = font
        if first == 10 and not heading:
            cell.number_format = number_format
        cell.alignment = Alignment(vertical="top", horizontal="right" if first == 10 else "left", wrap_text=True)
        if heading:
            cell.fill = PatternFill(fill_type="solid", fgColor="E7E6E6")
    worksheet.row_dimensions[row].height = height


def delivery_run_sheet_product_display(order):
    return "".join(text for text, _ in _product_display_parts(order))


def _product_display_parts(order):
    parts = []
    for line in getattr(order, "product_lines_snapshot", None) or []:
        product_name = str(getattr(line, "product_name", "") or "").strip()
        product_code = str(getattr(line, "product_code", "") or "").strip()
        quantity = getattr(line, "quantity", None)
        unit = str(getattr(line, "unit", "") or "").strip()
        if not product_name and not product_code:
            continue
        identity = product_name or product_code
        quantity_text = " ".join(
            part for part in (_display_number(quantity), unit) if part
        )
        package_quantity = getattr(line, "package_quantity", None)
        package_unit = str(getattr(line, "package_unit", "") or "").strip()
        package_text = _package_display(package_quantity, package_unit)
        detail = package_text or quantity_text
        if parts:
            parts.append(("\n", False))
        parts.append((identity, False))
        if detail:
            parts.append((" - ", False))
            has_quantity = bool(package_text) or (
                _numeric_value(quantity) is not None and not isinstance(quantity, bool)
            )
            parts.append((detail, has_quantity))
    if parts:
        return parts
    return [(str(getattr(order, "product_snapshot", "") or "").strip(), False)]


def _product_rich_text(parts, offset, length):
    blocks = []
    position = 0
    for text, is_quantity in parts:
        stop = position + len(text)
        start = max(offset, position)
        end = min(offset + length, stop)
        if start < end:
            font = InlineFont(b=True, sz=PRODUCT_FONT_SIZE,
                              color=PRODUCT_QUANTITY_COLOR if is_quantity else "000000")
            fragment = text[start - position:end - position]
            if blocks and blocks[-1].font == font:
                blocks[-1].text += fragment
            else:
                blocks.append(TextBlock(font, fragment))
        position = stop
    # Excel rejects formatted whitespace-only runs; inherit the black cell style.
    return CellRichText([block.text if block.text.isspace() else block for block in blocks])


def _package_display(quantity, unit):
    numeric = _numeric_value(quantity)
    if numeric is None or isinstance(quantity, bool) or not unit:
        return ""
    if str(unit).strip().upper() == "CARTON":
        return f"{_display_number(numeric)} {'Carton' if numeric == 1 else 'Cartons'}"
    weight_match = _PACKAGE_UNIT_BAG_WEIGHT.fullmatch(unit)
    if weight_match and numeric >= 0:
        weight = _numeric_value(weight_match.group(1))
        if weight is not None and weight > 0:
            return f"{_display_number(weight)}kg x {_display_number(numeric)}Bag"
    return f"{_display_number(numeric)} {unit}"


def _delivery_run_sheet_line_weight_kg(line):
    carton_weight = cartonized_product_weight_kg(line)
    if carton_weight is not None:
        return carton_weight
    unit = str(getattr(line, "unit", "") or "").strip().upper()
    if unit in {"KG", "KGS"}:
        return _numeric_value(getattr(line, "quantity", None))

    package_quantity = _numeric_value(getattr(line, "package_quantity", None))
    if package_quantity is None or package_quantity <= 0:
        return None

    product_code = str(getattr(line, "product_code", "") or "").strip()
    code_match = _PRODUCT_CODE_KG_SUFFIX.search(product_code)
    if code_match:
        return float(code_match.group(1)) * package_quantity

    package_unit = str(getattr(line, "package_unit", "") or "").strip()
    package_match = _PACKAGE_UNIT_BAG_WEIGHT.fullmatch(package_unit)
    if package_match:
        weight_per_bag = float(package_match.group(1))
        return weight_per_bag * package_quantity if weight_per_bag > 0 else None
    return None


def _delivery_run_sheet_weight_total(order):
    total = sum(
        weight
        for line in getattr(order, "product_lines_snapshot", None) or []
        if (weight := _delivery_run_sheet_line_weight_kg(line)) is not None
    )
    return "" if total == 0 else int(total) if total.is_integer() else total


def _numeric_value(value):
    if value is None or value == "":
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _display_number(value):
    if value is None or value == "":
        return ""
    numeric = float(value)
    return str(int(numeric)) if numeric.is_integer() else str(numeric)


def _wrapped_line_count(value, column_width, font_size=BODY_FONT_SIZE):
    return len(_wrapped_lines(value, column_width, font_size))


def _wrapped_lines(value, column_width, font_size=BODY_FONT_SIZE):
    # Excel column units use the default 11pt font's digit width (~7px).
    usable_width = max(font_size, (float(column_width) * 7 + 5) * 0.75 - 6)
    lines = []
    paragraphs = str(value or "").split("\n")
    for paragraph_index, paragraph in enumerate(paragraphs):
        if not paragraph:
            lines.append("")
        while paragraph:
            width = 0
            end = 0
            last_break = 0
            for index, character in enumerate(paragraph):
                if unicodedata.combining(character):
                    em = 0
                elif unicodedata.east_asian_width(character) in {"W", "F"}:
                    em = 1
                elif character in "MW@#%&":
                    em = 0.9
                elif character in "ilI.,'!:;|" or character.isspace():
                    em = 0.3
                else:
                    em = 0.68 if character.isupper() else 0.56
                width += em * font_size * 1.05
                if end and width > usable_width:
                    break
                end = index + 1
                if character.isspace():
                    last_break = end
            if end < len(paragraph) and last_break:
                end = last_break
            lines.append(paragraph[:end])
            paragraph = paragraph[end:]
        if paragraph_index < len(paragraphs) - 1:
            lines[-1] += "\n"
    return lines


def _unique_sheet_name(driver_name, used_sheet_names, trip_no=None):
    base_name = _INVALID_SHEET_NAME_CHARACTERS.sub(" ", str(driver_name or "Driver"))
    base_name = " ".join(base_name.split()).strip("'") or "Driver"
    if trip_no is not None:
        base_name = base_name.strip() or "Driver"
    trip_suffix = f" - Trip {1 if trip_no == 'trip1' else 2}" if trip_no is not None else ""
    candidate = f"{base_name[:31 - len(trip_suffix)]}{trip_suffix}"
    sequence = 2
    while candidate.casefold() in used_sheet_names:
        suffix = f" ({sequence})"
        candidate = f"{base_name[:31 - len(suffix) - len(trip_suffix)]}{suffix}{trip_suffix}"
        sequence += 1
    used_sheet_names.add(candidate.casefold())
    return candidate


def _display_date(value):
    return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")


def _write_order_row(worksheet, row_index, row_no, order, border):
    product_parts = _product_display_parts(order)
    product_display = "".join(text for text, _ in product_parts)
    values = [
        row_no,
        order.company_name_snapshot or "",
        order.suburb_snapshot or "",
        order.invoice_number_snapshot or "",
        product_display,
        _delivery_run_sheet_weight_total(order),
        _number_or_blank(order.pallet_quantity_snapshot),
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ]
    text_lines = {
        column: _wrapped_lines(values[column - 1], COLUMN_WIDTHS[letter], size)
        for column, letter, size in (
            (2, "B", BODY_FONT_SIZE), (3, "C", BODY_FONT_SIZE),
            (4, "D", BODY_FONT_SIZE), (5, "E", PRODUCT_FONT_SIZE),
        )
    }
    # A row must fit both Excel's native limit and the first page below the form.
    usable_height = (
        210 / 25.4 * 72
        - (worksheet.page_margins.top + worksheet.page_margins.bottom) * 72
        - sum(worksheet.row_dimensions[index].height for index in range(1, 9))
        - 12
    )
    max_lines = max(1, int((min(EXCEL_MAX_ROW_HEIGHT, usable_height) - BODY_ROW_PADDING)
                           / max(BODY_LINE_HEIGHT, PRODUCT_LINE_HEIGHT)))
    line_count = max(map(len, text_lines.values()))
    if line_count > max_lines:
        # A fragment can end in an original newline; reserve its trailing line.
        max_lines = max(1, max_lines - 1)
    parts = math.ceil(line_count / max_lines)
    product_offset = 0
    for part in range(parts):
        row_values = list(values) if part == 0 else [""] * 14
        if parts > 1:
            row_values[0] = row_no if part == 0 else f"{row_no}\ncont."
            for column, lines in text_lines.items():
                row_values[column - 1] = "".join(lines[part * max_lines:(part + 1) * max_lines])
        product_fragment = row_values[4]
        if product_fragment:
            # Slice semantic runs at the existing continuation's character boundaries.
            row_values[4] = _product_rich_text(product_parts, product_offset, len(product_fragment))
        product_offset += len(product_fragment)
        _write_order_cells(worksheet, row_index + part, row_values, border)
    return parts


def _write_order_cells(worksheet, row_index, values, border):
    for column_index, value in enumerate(values, start=1):
        cell = worksheet.cell(row=row_index, column=column_index, value=value)
        cell.font = Font(
            bold=column_index == 5,
            size=PRODUCT_FONT_SIZE if column_index == 5 else BODY_FONT_SIZE,
        )
        cell.border = border
        cell.alignment = Alignment(
            horizontal="center"
            if column_index in {1, 4, 6, 7, 8, 9, 10, 11, 14}
            else "left",
            vertical="top",
            wrap_text=column_index in {2, 3, 4, 5, 13} or column_index == 1 and isinstance(value, str),
            shrink_to_fit=False,
        )
        if column_index in {6, 7, 14} and value != "":
            cell.number_format = "General"
    body_lines = max(
        _wrapped_line_count(values[0], COLUMN_WIDTHS["A"]),
        _wrapped_line_count(values[1], COLUMN_WIDTHS["B"]),
        _wrapped_line_count(values[2], COLUMN_WIDTHS["C"]),
        _wrapped_line_count(values[3], COLUMN_WIDTHS["D"]),
    )
    product_lines = _wrapped_line_count(
        values[4],
        COLUMN_WIDTHS["E"],
        PRODUCT_FONT_SIZE,
    )
    worksheet.row_dimensions[row_index].height = max(
        MIN_BODY_ROW_HEIGHT,
        BODY_LINE_HEIGHT * body_lines + BODY_ROW_PADDING,
        PRODUCT_LINE_HEIGHT * product_lines + BODY_ROW_PADDING,
    )


def _write_empty_row(worksheet, row_index, row_no, border):
    for column_index in range(1, 15):
        cell = worksheet.cell(row=row_index, column=column_index, value=row_no if column_index == 1 else "")
        cell.font = Font(size=BODY_FONT_SIZE)
        cell.border = border
        cell.protection = Protection(locked=False)
        cell.alignment = Alignment(horizontal="center" if column_index == 1 else "left", vertical="top")
    worksheet.row_dimensions[row_index].height = MIN_BODY_ROW_HEIGHT


def _number_or_blank(value):
    return "" if value is None else value


def _rego_snapshot_display(run_sheet):
    rego = str(getattr(run_sheet, "vehicle_rego_snapshot", "") or "").strip()
    return rego or "Not selected"


def _apply_column_widths(worksheet):
    for column_letter, width in COLUMN_WIDTHS.items():
        worksheet.column_dimensions[column_letter].width = width
    worksheet.freeze_panes = "B9"


def _apply_row_heights(worksheet):
    row_heights = {
        1: 21,
        2: 21,
        3: 21,
        4: 15,
        5: 15.75,
        6: 15.75,
        7: 15,
        8: 21,
    }
    for row_index, height in row_heights.items():
        worksheet.row_dimensions[row_index].height = height


def _save(workbook):
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
