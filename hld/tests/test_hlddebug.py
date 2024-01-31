#!usr/bin/env python3

import unittest
import z3

import hldast
import hlddebug
import hldparser
import hldsemantic

class TestHldDebug(unittest.TestCase):
    def test_assignments(self):
        program = '''
#post z == x + 2 * y
proc linear(x, y) {
  a := x;
  b := y;
  a := a + b;
  z := b;
  z := z + a;
}
'''
        ast, = hldparser.parser.parse_string(program, parse_all=True)
        assert isinstance(ast, hldast.Proc)
        variables = hldsemantic.check_declaration(ast)
        pre = hlddebug.get_pre(ast, hlddebug.Correctness.PARTIAL, variables)
        self.assertEqual(pre, True)

    def test_ifelse(self):
        program = '''
#post (y >= x || z == y) && (x > y || z == x)
proc min(x, y) {
  if x <= y {
    z := x;
  } else {
    z := y;
  }
}
'''
        ast, = hldparser.parser.parse_string(program, parse_all=True)
        assert isinstance(ast, hldast.Proc)
        variables = hldsemantic.check_declaration(ast)
        pre = hlddebug.get_pre(ast, hlddebug.Correctness.PARTIAL, variables)
        self.assertEqual(pre, True)

    def test_while_partial(self):
        program = '''
#post total == n * (n - 1)
proc sum(n) {
  i := 0;
  total := 0;
  #invariant total == i * (i - 1)
  while i != n {
    total := total + 2 * i;
    i := i + 1;
  }
}
'''
        ast, = hldparser.parser.parse_string(program, parse_all=True)
        assert isinstance(ast, hldast.Proc)
        variables = hldsemantic.check_declaration(ast)
        pre = hlddebug.get_pre(ast, hlddebug.Correctness.PARTIAL, variables)
        self.assertEqual(pre, True)

    def test_while_total(self):
        program = '''
#post total == n * (n - 1)
proc sum(n) {
  i := 0;
  total := 0;
  #invariant total == i * (i - 1)
  #variant n - i
  while i != n {
    total := total + 2 * i;
    i := i + 1;
  }
}
'''
        ast, = hldparser.parser.parse_string(program, parse_all=True)
        assert isinstance(ast, hldast.Proc)
        variables = hldsemantic.check_declaration(ast)
        pre = hlddebug.get_pre(ast, hlddebug.Correctness.TOTAL, variables)
        expected = z3.Int('n') >= 0
        s = z3.Solver()
        s.add(expected != pre)
        self.assertEqual(s.check(), z3.unsat)
