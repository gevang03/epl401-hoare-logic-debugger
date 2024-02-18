#!/usr/bin/env python3

import unittest
import pyparsing as pp

import hldast
import hldparser

from typing import Any
from operator import attrgetter

class TestHldParser(unittest.TestCase):
    def _test(self, parser: pp.ParserElement, input: str, type: type, field_values: dict[str, Any]):
        res, = parser.parse_string(input, parse_all=True)
        self.assertIsInstance(res, type)
        for field, value in field_values.items():
            self.assertEqual(attrgetter(field)(res), value)

    def _test_value(self, parser: pp.ParserElement, input: str, value, type: type):
        return self._test(parser, input, type, {'value' : value})

    def test_bool_literal_false(self):
        self._test_value(hldparser.bool_lit, 'false', False, hldast.BoolLiteral)

    def test_bool_literal_true(self):
        self._test_value(hldparser.bool_lit, 'true', True, hldast.BoolLiteral)

    def test_int_literal(self):
        value = 12345
        self._test_value(hldparser.int_lit, str(value), value, hldast.IntLiteral)

    def test_identifer(self):
        value = '_ident1'
        self._test_value(hldparser.identifier, value, value, hldast.Identifier)

    def test_prefix_arith(self):
        self._test(hldparser.expr, '-(a+b)', hldast.PrefixArithmeticExpr, {'op': '-'})
        self._test(hldparser.expr, '+(b*3)', hldast.PrefixArithmeticExpr, {'op': '+'})

    def test_prefix_logical(self):
        self._test(hldparser.expr, '!false', hldast.PrefixLogicalExpr, {'op': '!'})

    def test_infix_arith(self):
        self._test(hldparser.expr, '(a+1)', hldast.InfixArithmeticExpr, {'op': '+'})
        self._test(hldparser.expr, '5-(b*3)', hldast.InfixArithmeticExpr, {'op': '-'})
        self._test(hldparser.expr, '(c*3)', hldast.InfixArithmeticExpr, {'op': '*'})
        self._test(hldparser.expr, 'a * c + d', hldast.InfixArithmeticExpr, {'op': '+'})

    def test_infix_relational(self):
        self._test(hldparser.expr, 'b<2', hldast.InfixRelationalExpr, {'op': '<'})
        self._test(hldparser.expr, 'foo <= bar', hldast.InfixRelationalExpr, {'op': '<='})
        self._test(hldparser.expr, '1 - 3 == baz', hldast.InfixRelationalExpr, {'op': '=='})
        self._test(hldparser.expr, ' -3 != baz', hldast.InfixRelationalExpr, {'op': '!='})
        self._test(hldparser.expr, ' 5  > a * 4', hldast.InfixRelationalExpr, {'op': '>'})
        self._test(hldparser.expr, '1>=2', hldast.InfixRelationalExpr, {'op': '>='})

    def test_infix_logical(self):
        self._test(hldparser.expr, 'p || q', hldast.InfixLogicalExpr, {'op': '||'})
        self._test(hldparser.expr, 'p1 && p2', hldast.InfixLogicalExpr, {'op': '&&'})
        self._test(hldparser.expr, 'p && q || r', hldast.InfixLogicalExpr, {'op': '||'})

    def test_ternary(self):
        values = {'cond.value': False, 'then_expr.value': 1, 'else_expr.value': 2}
        self._test(hldparser.expr, 'false ? 1 : 2', hldast.TernaryExpr, values)

    def test_assignment(self):
        self._test(hldparser.assignment, 'foo := 1 + 7;', hldast.Assignment, {'dest.value' : 'foo', 'value.op': '+'})

    def test_block(self):
        self._test(hldparser.block, ' { foo := -4; bar := 9 + 3; }', hldast.Block, {})

    def test_if_else(self):
        self._test(hldparser.ifelse, 'if false {} else {}', hldast.IfElse, {'cond.value': False})
        field_values = {'cond.value': False, 'else_block.cond.value': True}
        self._test(hldparser.ifelse, 'if false {} else if true {} else {}', hldast.IfElse, field_values)

    def test_while(self):
        self._test(hldparser.while_, 'while false {}', hldast.While, {'cond.value': False})

    def test_assert(self):
        self._test(hldparser.assert_, 'assert false;', hldast.Assert, {'expr.value': False})

    def test_return(self):
        self._test(hldparser.return_, 'return 35;', hldast.Return, {'expr.value': 35})

    def test_proc(self):
        self._test(hldparser.proc, 'proc foo() {}', hldast.Proc, {'name.value': 'foo'})
