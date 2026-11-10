"""Command line for the armorkit foundation: registry, parts tables, measurements and client fixtures."""
import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = 'tools.armorkit'

from . import registry, tables


def write_json(path, document):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=1) + '\n', encoding='utf-8', newline='\n')


def command_registry(args):
    parts = registry.load(args.registry, publish=args.publish)
    if args.handoff:
        write_json(args.handoff, registry.handoff(parts))
    print(json.dumps({'parts': len(parts), 'slots': {slot: registry.numbers(parts, slot) for slot in registry.SLOTS
                                                     if registry.numbers(parts, slot)}}))


def command_tables(args):
    parts = registry.load(args.registry, publish=args.publish)
    stock = {table: (Path(args.stock) / (table + '.2da')).read_bytes().decode('cp1252') for table in registry.TABLES}
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    report = []
    for table, text in tables.generate_all(stock, parts).items():
        report.append(tables.check(table, text, parts, stock[table]))
        (output / (table + '.2da')).write_bytes(text.encode('cp1252'))
    print(json.dumps(report))


def command_measure(args):
    from . import measure
    output = Path(args.output)
    write_json(output / 'seam-contract.json', measure.seam_contract(args.body_pack, [args.body_pack, *args.supermodels]))
    write_json(output / 'head-envelopes.json', measure.head_envelopes(args.head_pack, args.body_pack))
    print(json.dumps({'written': [str(output / 'seam-contract.json'), str(output / 'head-envelopes.json')]}))


def command_fixture(args):
    from . import client
    from . import client_fixture as fixture
    spec = json.loads(Path(args.spec).read_text(encoding='utf-8'))
    record = fixture.build(spec, args.output, args.nwn_root)
    if args.run:
        record['evidence'] = client.run(args.nwn_root, record, Path(args.output) / 'captures')
    print(json.dumps(record))


def main(argv=None):
    parser = argparse.ArgumentParser(prog='armorkit', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('registry', help='validate a registry and optionally write the SR_NWN handoff file')
    p.add_argument('registry'); p.add_argument('--publish', action='store_true'); p.add_argument('--handoff')
    p.set_defaults(run=command_registry)
    p = commands.add_parser('tables', help='generate the twelve parts tables from a registry and stock tables')
    p.add_argument('registry'); p.add_argument('--stock', required=True, help='folder holding the stock parts_*.2da files')
    p.add_argument('--output', required=True); p.add_argument('--publish', action='store_true')
    p.set_defaults(run=command_tables)
    p = commands.add_parser('measure', help='measure the seam contract and head envelopes from pack folders')
    p.add_argument('--body-pack', required=True); p.add_argument('--head-pack', required=True)
    p.add_argument('--supermodels', action='append', default=[], help='folder of extracted stock animation models')
    p.add_argument('--output', required=True)
    p.set_defaults(run=command_measure)
    p = commands.add_parser('fixture', help='build an isolated client fixture, and optionally run it')
    p.add_argument('--spec', required=True); p.add_argument('--output', required=True)
    p.add_argument('--nwn-root', required=True, help='game install folder (from the local runtime binding)')
    p.add_argument('--run', action='store_true')
    p.set_defaults(run=command_fixture)
    args = parser.parse_args(argv)
    args.run(args)


if __name__ == '__main__':
    main()
