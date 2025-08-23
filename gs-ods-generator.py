"""
Generate GS ods
"""

import argparse
import asyncio
import sys
import traceback
from datetime import datetime

import aiohttp
import country_converter as coco
from lxml import etree, html
from odf.opendocument import load
from odf.table import Table, TableCell, TableRow
from odf.text import P

TEMPLATE_FILE = "Tennis-Template.ods"
TABLE_XPATH = "/html/body/div[@class='mw-page-container']" \
    "/div[@class='mw-page-container-inner']/div[@class='mw-content-container']" \
    "/main[@id='content']/div[@id='bodyContent']/div[@id='mw-content-text']" \
    "/div/div/h4[contains(text(), 'Section')]/parent::*/following-sibling::table[1]"


async def fetch_data(session: aiohttp.client.ClientSession, url: str):
    try:
        async with session.get(url) as response:
            tree = html.fromstring(await response.text())

            row = 2
            results = []
            tables = tree.xpath(TABLE_XPATH)
            for table in tables:
                seeds = list(map(str.strip, table.xpath(
                    "./tbody/tr/td/a/parent::*/preceding-sibling::td/text()")))

                names = []
                countries = []

                for cell in table.xpath("./tbody/tr/td/a/parent::*"):
                    names.append(cell.xpath("./a/text()")[0])
                    country = cell.xpath(
                        "./span[@class='flagicon']/span/a/@title")
                    countries.append(country[0] if country else "")
                codes = coco.convert(names=countries, to='ISO3')
                codes = [c if c != "not found" else "" for c in codes]

                for i, seed in enumerate(seeds):
                    results.append((row, 0, seed))
                    results.append((row, 1, names[i]))
                    results.append((row, 2, codes[i]))
                    row += 1

            return results
    except (aiohttp.ClientConnectionError, aiohttp.ClientResponseError,
            asyncio.TimeoutError, ValueError, TypeError, etree.XMLSyntaxError) as e:
        print(f":: Error fetching data from: {url}: {e}")
        traceback.print_exc()
        return None


def save_ods_data(template_file_path: str, save_file_path: str, data):
    try:
        doc = load(template_file_path)

        sheets = {}
        for t in doc.getElementsByType(Table):
            sheets[t.getAttribute('name')] = t

        for sheet_name, sheet_data in data.items():
            if sheet_name not in sheets:
                raise ValueError(f"Sheet '{sheet_name}' not found.")

            table = sheets[sheet_name]

            for row_index, col_index, value in sheet_data:

                rows = table.getElementsByType(TableRow)
                if row_index >= len(rows):
                    raise IndexError("Row index is out of range.")

                row = rows[row_index]

                cells = row.getElementsByType(TableCell)
                if col_index >= len(cells):
                    raise IndexError("Column index is out of range")

                cell = cells[col_index]

                for child in cell.childNodes:
                    cell.removeChild(child)

                p_element = P(text=str(value))
                cell.addElement(p_element)
                cell.setAttribute('valuetype', 'string')
                cell.setAttribute('value', None)

        doc.save(save_file_path)
        print(f":: saved file '{save_file_path}'.")

    except (FileNotFoundError, ValueError, IndexError) as e:
        print(f":: error: {e}")
        sys.exit(1)


def parse_args():
    """Parses command line arguments"""

    parser = argparse.ArgumentParser(
        description="Tennis Temple Match Predictor")
    parser.add_argument("-t", "--timeout", type=int, default=30,
                        help="Timeout to use during network operations (default: 30)")
    parser.add_argument("-i", "--input-file", type=str, default=TEMPLATE_FILE,
                        help=f"Input template file to use (default: {TEMPLATE_FILE})")
    parser.add_argument("--slam", type=str, choices=["aus", "fre", "wim", "us"], required=True,
                        help="Grand Slam to process")
    parser.add_argument("--year", type=int, default=datetime.now().year,
                        help="Year to process")

    return parser.parse_args()


async def main():
    args = parse_args()

    if args.slam == "aus":
        wiki_t = "Australian_Open"
    elif args.slam == "fre":
        wiki_t = "French_Open"
    elif args.slam == "wim":
        wiki_t = "Wimbledon_Championships"
    else:
        wiki_t = "US_Open"

    wiki_m = f"https://en.wikipedia.org/wiki/{args.year}_{wiki_t}_%E2%80%93_Men's_singles"
    wiki_w = f"https://en.wikipedia.org/wiki/{args.year}_{wiki_t}_%E2%80%93_Women's_singles"
    file_name = f"{args.year}-{wiki_t}.ods"

    cto = aiohttp.ClientTimeout(total=args.timeout)
    async with aiohttp.ClientSession(timeout=cto) as session:
        results_m = await fetch_data(session, wiki_m)
        results_w = await fetch_data(session, wiki_w)
        results = {
            "ML": results_m,
            "FL": results_w,
        }

        save_ods_data(args.input_file, file_name, results)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
