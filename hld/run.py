#!/usr/bin/env python3

import hldast
import hldcompiler
import hlddebug
import hldinterpreter
import hldparser
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
    p.add_option('--run',
                 action='store_true',
                 default=False,
                 help='run program'
                 )
    p.add_option('--dis',
                 action='store_true',
                 default=False,
                 help='disassemble vm'
                 )
    return p.parse_args(argv)

def main(argv: list[str]) -> None | int:
    options, args = parse_args(argv)
    proc, = hldparser.parser.parse_file(args[1], parse_all=True)
    assert type(proc) == hldast.Proc
    try:
        hldsemantic.check_declaration(proc)
    except RuntimeError as e:
        print(f'{args[1]}: {e.args[0]}')
        return 1
    if options.run:
        assert type(proc) == hldast.Proc
        vars, prog = hldcompiler.compile_proc(proc)
        vm = hldinterpreter.Vm(prog)
        result = vm.run(vars)
        print(result)
    elif options.dis:
        vars, prog = hldcompiler.compile_proc(proc)
        for i, (opcode, arg) in enumerate(prog):
            print(f'{i:04x} {opcode.name} {arg:x}')
    else:
        assert options.correctness == 'partial'
        pre = hlddebug.get_pre(proc)
        print(f'#pre {pre}')

if __name__ == '__main__':
    status = main(sys.argv)
    sys.exit(status)
