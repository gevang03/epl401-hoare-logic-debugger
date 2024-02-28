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
#post result == x + 2 * y
proc linear(x, y) {
  a := x;
  b := y;
  a := a + b;
  z := b;
  z := z + a;
  return z;
}
'''
        ast = hldparser.parser.parse_string(program, parse_all=True).as_list()
        self.assertIsInstance(ast, list)
        decls, call_graph = hldsemantic.check_program(ast)
        pre = hlddebug.get_pre(ast, hlddebug.Correctness.PARTIAL, decls, call_graph)['linear']
        self.assertEqual(pre, True)

    def test_ifelse(self):
        program = '''
#pre true
#post result == (x < y ? x : y)
proc min(x, y) {
  if x < y {
    z := x;
  } else {
    z := y;
  }
  return z;
}
'''
        ast = hldparser.parser.parse_string(program, parse_all=True).as_list()
        self.assertIsInstance(ast, list)
        decls, call_graph = hldsemantic.check_program(ast)
        pre = hlddebug.get_pre(ast, hlddebug.Correctness.PARTIAL, decls, call_graph)['min']
        self.assertEqual(pre, True)

    def test_while_partial(self):
        program = '''
#post result == n * (n - 1)
proc sum(n) {
  i := 0;
  total := 0;
  #invariant total == i * (i - 1)
  while i != n {
    total := total + 2 * i;
    i := i + 1;
  }
  return total;
}
'''
        ast = hldparser.parser.parse_string(program, parse_all=True).as_list()
        self.assertIsInstance(ast, list)
        decls, call_graph = hldsemantic.check_program(ast)
        pre = hlddebug.get_pre(ast, hlddebug.Correctness.PARTIAL, decls, call_graph)['sum']
        self.assertEqual(pre, True)

    def test_while_total(self):
        program = '''
#post result == n * (n - 1)
proc sum(n) {
  i := 0;
  total := 0;
  #invariant total == i * (i - 1)
  #variant n - i
  while i != n {
    total := total + 2 * i;
    i := i + 1;
  }
  return total;
}
'''
        ast = hldparser.parser.parse_string(program, parse_all=True).as_list()
        self.assertIsInstance(ast, list)
        decls, call_graph = hldsemantic.check_program(ast)
        pre = hlddebug.get_pre(ast, hlddebug.Correctness.TOTAL, decls, call_graph)['sum']
        expected = z3.Int('n') >= 0
        s = z3.Solver()
        s.add(expected != pre)
        self.assertEqual(s.check(), z3.unsat)

    def test_call_partial(self):
        program = '''
fn sum(n) := n == 0 ? 0 : n + sum(n - 1);

#post result == sum(n)
proc sum_rec(n) {
  if n == 0 {
    return 0;
  } else {
    t := sum_rec(n - 1);
    return t + n;
  }
}
'''
        ast = hldparser.parser.parse_string(program, parse_all=True).as_list()
        self.assertIsInstance(ast, list)
        decls, call_graph = hldsemantic.check_program(ast)
        pre = hlddebug.get_pre(ast, hlddebug.Correctness.PARTIAL, decls, call_graph)['sum_rec']
        expected = z3.BoolVal(True)
        s = z3.Solver()
        s.add(expected != pre)
        self.assertEqual(s.check(), z3.unsat)

    def test_call_total(self):
        program = '''
fn sum(n) := n <= 0 ? 0 : n + sum(n - 1);

#post result == sum(n)
#variant n
proc sum_rec(n) {
  if n == 0 {
    return 0;
  } else {
    t := sum_rec(n - 1);
    return t + n;
  }
}
'''
        ast = hldparser.parser.parse_string(program, parse_all=True).as_list()
        self.assertIsInstance(ast, list)
        decls, call_graph = hldsemantic.check_program(ast)
        pre = hlddebug.get_pre(ast, hlddebug.Correctness.TOTAL, decls, call_graph)['sum_rec']
        expected = z3.Int('n') >= 0
        s = z3.Solver()
        s.add(expected != pre)
        self.assertEqual(s.check(), z3.unsat)
