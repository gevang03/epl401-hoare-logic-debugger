#!/usr/bin/env python3

import hldast
import hldcompiler
import hlddebug
import hldinterpreter
import hldparser
import hldsemantic

import optparse
import pyparsing
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
                 metavar='\'FN [ARGS...]\'',
                 action='store',
                 type='string',
                 help='run program with entry point FN with ARGS'
                 )
    p.add_option('--dis',
                 action='store_true',
                 default=False,
                 help='disassemble vm'
                 )
    return p.parse_args(argv)

def run(filename: str, call: str) -> None | int:
    decls = hldparser.parser.parse_file(filename, parse_all=True).as_list()
    assert isinstance(decls, list)
    hldsemantic.check_program(decls)
    try:
        proc, *args = call.split()
        args = list(map(int, args))
    except ValueError:
        print('error: malformed entry point argument', file=sys.stderr)
        exit(1)
    procs, prog = hldcompiler.compile_program(decls)
    try:
        start = procs[proc]
    except KeyError:
        print(f'error: proc `{proc}` is not defined', file=sys.stderr)
        return 1
    vm = hldinterpreter.Vm(prog)
    result = vm.run(start, args)
    print(result)

def dis(filename: str) -> None | int:
    decls = hldparser.parser.parse_file(filename, parse_all=True).as_list()
    assert isinstance(decls, list)
    hldsemantic.check_program(decls)
    _, prog = hldcompiler.compile_program(decls)
    for i, (opcode, arg) in enumerate(prog):
        print(f'{i:04x} {opcode.name} {arg:04x}')

def debug(filename: str, correctness: hlddebug.Correctness):
    decls = hldparser.parser.parse_file(filename, parse_all=True).as_list()
    assert isinstance(decls, list)
    symtab, call_graph = hldsemantic.check_program(decls)
    pres = hlddebug.get_pre(decls, correctness, symtab, call_graph)
    for sym, pre in pres.items():
        print(f'proc {sym}(...) {{...}} requires `{pre}`')

def main(argv: list[str]) -> None | int:
    options, args = parse_args(argv)
    filename = args[1]
    try:
        if options.run != None:
            assert isinstance(options.run, str)
            return run(filename, options.run)
        elif options.dis:
            return dis(filename)
        else:
            correctness = hlddebug.Correctness(options.correctness)
            return debug(filename, correctness)
    except OSError as os_err:
        print(f'error: {os_err.filename}: {os_err.strerror}', file=sys.stderr)
        return 1
    except pyparsing.exceptions.ParseBaseException as pe:
        print(pe.explain(depth=0), file=sys.stderr)
        return 1
    except hldast.HLDError as pe:
        print(f'{args[1]}:{pe.args[0]}', file=sys.stderr)
        return 1

if __name__ == '__main__':
    status = main(sys.argv)
    sys.exit(status)
