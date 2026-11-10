"""Generate the twelve parts_*.2da tables from the registry.

The client reads these tables by position, so every row up to the highest part number must exist
(docs/armorkit/spikes.md, section 1). Stock rows are copied as they are; new live rows carry no cost
and no armor value; the rows between them are padding.
"""
from . import registry
from .registry import require

HEADER = '2DA V2.0'
PADDING = '****'
# Rows the stock game ships, by table: 0-200 everywhere except the robe table, which stops at 38.
STOCK_ROWS = {table: 201 for table in registry.TABLES} | {'parts_robe': 39}
LIVE = {'COSTMODIFIER': '0', 'ACBONUS': '0.00'}
TABLE_SLOT = {row['table']: slot for slot, row in registry.SLOTS.items()}


def parse(text):
    """(columns, rows) of a 2DA; each row is its cells without the leading index, which must count from 0."""
    lines = [line for line in text.replace('\r\n', '\n').split('\n')]
    require(lines and lines[0].strip() == HEADER, 'Not a 2DA V2.0 table')
    body = [line for line in lines[1:] if line.strip()]
    require(body, 'Table has no column row')
    columns = body[0].split()
    rows = []
    for index, line in enumerate(body[1:]):
        cells = line.split()
        require(cells[0] == str(index), f'Row {index} is labelled {cells[0]}: rows must count from 0 with no gaps')
        require(len(cells) == len(columns) + 1, f'Row {index} has {len(cells) - 1} cells for {len(columns)} columns')
        rows.append(cells[1:])
    return columns, rows


def live_row(columns, part):
    """Cells of a new live row: no cost, no armor value, robe hide flags from the part."""
    hidden = set(part.get('hide', ()))
    cells = []
    for column in columns:
        if column in LIVE:
            cells.append(LIVE[column])
        else:
            require(column.startswith('HIDE') and column[4:] in registry.ROBE_HIDES, 'Unknown parts table column ' + column)
            cells.append('1' if column[4:] in hidden else '0')
    return cells


def generate(table, stock_text, parts):
    """The table's text: stock rows byte for byte, then padding and live rows up to the highest number."""
    require(table in TABLE_SLOT, 'Unknown parts table ' + str(table))
    columns, rows = parse(stock_text)
    require(columns[:2] == ['COSTMODIFIER', 'ACBONUS'], table + ': unexpected stock columns')
    require(len(rows) == STOCK_ROWS[table], f'{table}: expected {STOCK_ROWS[table]} stock rows, found {len(rows)}')
    live = {part['number']: part for part in parts if part['slot'] == TABLE_SLOT[table]}
    require(len(live) == sum(part['slot'] == TABLE_SLOT[table] for part in parts), table + ': duplicate part number')
    require(all(number >= registry.FIRST_NUMBER for number in live), table + ': a new part reuses a stock or buffer row')
    stock_lines = [line for line in stock_text.replace('\r\n', '\n').split('\n')]
    while stock_lines and not stock_lines[-1].strip():
        stock_lines.pop()
    lines = list(stock_lines)
    width = max(len(str(max(live, default=0))), 4) + 1
    for number in range(len(rows), max(live, default=-1) + 1):
        cells = live_row(columns, live[number]) if number in live else [PADDING] * len(columns)
        lines.append(str(number).ljust(width) + ' '.join(cell.ljust(13) for cell in cells).rstrip())
    return '\r\n'.join(lines) + '\r\n'


def generate_all(stock, parts):
    """{table name: text} for all twelve tables; `stock` maps each table name to its stock text."""
    require(set(stock) == set(registry.TABLES), 'Stock text for exactly the twelve parts tables required')
    return {table: generate(table, stock[table], parts) for table in registry.TABLES}


def check(table, text, parts, stock_text=None):
    """Fail on a gap, a duplicate, a registry part without a live row, or a live row no part owns."""
    columns, rows = parse(text)  # parse rejects gaps and duplicate or missing indices
    stock = STOCK_ROWS[table]
    require(len(rows) >= stock, table + ': stock rows are missing')
    if stock_text is not None:
        require(parse(stock_text)[1] == rows[:stock], table + ': a stock row changed')
    slot = TABLE_SLOT[table]
    wanted = registry.numbers(parts, slot)
    require(len(set(wanted)) == len(wanted), table + ': duplicate part number in the registry')
    by_number = {part['number']: part for part in parts if part['slot'] == slot}
    for number in wanted:
        require(number < len(rows), f'{table}: registry part {number} has no row')
    for number in range(stock, len(rows)):
        expected = live_row(columns, by_number[number]) if number in by_number else [PADDING] * len(columns)
        require(rows[number] == expected, f'{table}: row {number} is not the {"live" if number in by_number else "padding"} row the registry implies')
    require(len(rows) == max([stock] + [number + 1 for number in wanted]), table + ': rows continue past the highest part number')
    return {'table': table, 'rows': len(rows), 'live': wanted}
