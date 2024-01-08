#!/usr/bin/env python3

import hldast
import hldparser
import hlddebug
import hldsemantic

import optparse
import sys

def parse_args(argv: list[str]) -> tuple[optparse.Values, list[str]]:
    usage = 'usage: %prog [options] filename'
    p = optparse.OptionParser(usage=usage)
    p.add_option('--total',
                 action='store_const',
                 default='partial',
                 const='total',
                 dest='correctness',
                 help='enforce total correctness instead of partial'
                 )
    p.add_option('--trace',
                 action='store_true',
                 default=False,
                 help='display inferences step by step'
                 )
    return p.parse_args(argv)

def main(argv: list[str]) -> None | int:
    options, args = parse_args(argv)
    try:
        with open(args[1]) as f:
            src = f.read()
    except Exception as e:
        print(e, file=sys.stderr)
        return 1
    proc, = hldparser.parser.parse_file(args[1], parse_all=True)
    assert type(proc) == hldast.Proc
    hldsemantic.check_proc(src, proc)
    pre = hlddebug.get_pre(proc)
    print(f'#pre {pre}')

if __name__ == '__main__':
    status = main(sys.argv)
    sys.exit(status)
