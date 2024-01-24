#!/usr/bin/env python3

import pyparsing as pp
from hldast import *

pp.ParserElement.enable_packrat()

_infix_arith_ops = { '+', '-', '*' }
_infix_log_ops = { '&&', '||' }
_infix_rel_ops = { '<', '<=', '==', '!=', '>', '>=' }

def infix_ctor(src: str, loc: int, tokens: pp.ParseResults) -> Expr:
    tokens, = tokens
    left = tokens[0]
    assert isinstance(left, Expr)
    for i in range(len(tokens) // 2):
        op = tokens[2 * i + 1]
        assert isinstance(op, str)
        right = tokens[2 * i + 2]
        assert isinstance(right, Expr)
        if op in _infix_arith_ops:
            left = InfixArithmeticExpr(src, loc, op, left, right)
        elif op in _infix_log_ops:
            left = InfixLogicalExpr(src, loc, op, left, right)
        else:
            assert op in _infix_rel_ops
            left = InfixRelationalExpr(src, loc, op, left, right)
    return left

def prefix_ctor(src: str, loc: int, tokens: pp.ParseResults) -> PrefixExpr:
    [op, expr], = tokens
    assert isinstance(op, str)
    assert isinstance(expr, Expr)
    if op in { '+', '-' }:
        return PrefixArithmeticExpr(src, loc, op, expr)
    else:
        assert op == '!'
        return PrefixLogicalExpr(src, loc, op, expr)

keywords = {
    'if', 'else', 'proc', 'while', 'true', 'false', 'return',
    '#pre', '#post', '#invariant', '#variant'
}
kw = {k: pp.Keyword(k) for k in keywords}
sup_kw = {k: pp.Suppress(v) for k, v in kw.items()}

identifier = pp.Regex('\\$?[a-zA-z_][a-zA-z0-9_]*')
identifier.add_condition(lambda s: s[0] not in keywords)
identifier.set_parse_action(lambda s, loc, toks: Identifier(s, loc, toks[0]))
int_lit = pp.pyparsing_common.integer.copy()
int_lit.set_parse_action(lambda s, loc, toks: IntLiteral(s, loc, int(toks[0])))
bool_lit = kw['true'] | kw['false']
bool_lit.set_parse_action(lambda s, loc, toks: BoolLiteral(s, loc, toks[0] == 'true'))

assign = pp.Suppress(':=')
semi = pp.Suppress(';')
left_brace = pp.Suppress('{')
right_brace = pp.Suppress('}')
left_paren = pp.Suppress('(')
right_paren = pp.Suppress(')')

unary_op = pp.one_of('+ - !')
mul_op = pp.Literal('*')
add_op = pp.one_of('+ -')
cmp_op = pp.one_of('<= < >= > == !=')
and_op = pp.Literal('&&')
or_op = pp.Literal('||')

assoc_table = [
    (unary_op, 1, pp.OpAssoc.RIGHT, prefix_ctor),
    (mul_op, 2, pp.OpAssoc.LEFT, infix_ctor),
    (add_op, 2, pp.OpAssoc.LEFT, infix_ctor),
    (cmp_op, 2, pp.OpAssoc.LEFT, infix_ctor),
    (and_op, 2, pp.OpAssoc.LEFT, infix_ctor),
    (or_op, 2, pp.OpAssoc.LEFT, infix_ctor),
]
expr = pp.infix_notation(int_lit | bool_lit | identifier, assoc_table)

precondition = sup_kw['#pre'] - expr
postcondition = sup_kw['#post'] - expr
invariant = sup_kw['#invariant'] - expr
variant = sup_kw['#variant'] - expr

statement = pp.Forward()
assignment = identifier - assign - expr - semi
assignment.set_parse_action(lambda s, loc, tokens: Assignment(s, loc, tokens[0], tokens[1]))
block = left_brace - pp.Group(statement[...], True) - right_brace
block.set_parse_action(lambda s, loc, tokens: Block(s, loc, *tokens))
ifelse = pp.Forward()
ifelse <<= sup_kw['if'] - expr - block - sup_kw['else'] - (ifelse | block)
ifelse.set_parse_action(lambda s, loc, tokens: IfElse(s, loc, *tokens))
while_ = pp.Opt(invariant, None) + pp.Opt(variant, None) + sup_kw['while'] - expr - block
while_.set_parse_action(lambda s, loc, tokens: While(s, loc, *tokens))
statement <<= ifelse | while_ | assignment

params = left_paren - pp.Opt(pp.Group(pp.DelimitedList(identifier), True), []) - right_paren

proc = pp.Opt(precondition, None) + pp.Opt(postcondition, None) +\
    sup_kw['proc'] - identifier - params - block
proc.set_parse_action(lambda s, loc, tokens: Proc(s, loc, *tokens))
parser = proc.ignore(pp.dbl_slash_comment)
