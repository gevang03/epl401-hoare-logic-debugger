#!/usr/bin/env python3

import pyparsing as pp
from hldast import *

pp.ParserElement.enable_packrat()

_infix_arith_ops = { '+', '-', '*', '/', '%' }
_infix_log_ops = { '&&', '||' }
_infix_rel_ops = { '<', '<=', '==', '!=', '>', '>=' }

def ternary_ctor(src: str, loc: int, toks: pp.ParseResults) -> TernaryExpr:
    [cond, q_mark, then_expr, colon, else_expr], = toks
    assert isinstance(cond, Expr)
    assert q_mark == '?'
    assert isinstance(then_expr, Expr)
    assert colon == ':'
    assert isinstance(else_expr, Expr)
    return TernaryExpr(src, loc, cond, then_expr, else_expr)

def infix_ctor(src: str, loc: int, toks: pp.ParseResults) -> Expr:
    toks, = toks
    left = toks[0]
    assert isinstance(left, Expr)
    for i in range(len(toks) // 2):
        op = toks[2 * i + 1]
        assert isinstance(op, str)
        right = toks[2 * i + 2]
        assert isinstance(right, Expr)
        if op in _infix_arith_ops:
            left = InfixArithmeticExpr(src, loc, op, left, right)
        elif op in _infix_log_ops:
            left = InfixLogicalExpr(src, loc, op, left, right)
        else:
            assert op in _infix_rel_ops
            left = InfixRelationalExpr(src, loc, op, left, right)
    return left

def prefix_ctor(src: str, loc: int, toks: pp.ParseResults) -> PrefixExpr:
    [op, expr], = toks
    assert isinstance(op, str)
    assert isinstance(expr, Expr)
    if op in { '+', '-' }:
        return PrefixArithmeticExpr(src, loc, op, expr)
    else:
        assert op == '!'
        return PrefixLogicalExpr(src, loc, op, expr)

keywords = {
    'assert', 'if', 'else', 'proc', 'fn', 'while', 'true', 'false', 'return', 'result',
    '#pre', '#post', '#invariant', '#variant'
}
kw = {k: pp.Keyword(k) for k in keywords}
sup_kw = {k: pp.Suppress(v) for k, v in kw.items()}

not_kw = ~pp.MatchFirst(kw.values())
identifier = not_kw + pp.Regex('[a-zA-z_][a-zA-z0-9_]*')
identifier.set_parse_action(lambda s, loc, toks: Identifier(s, loc, toks[0]))
int_lit = pp.pyparsing_common.integer.copy()
int_lit.set_parse_action(lambda s, loc, toks: IntLiteral(s, loc, int(toks[0])))
bool_lit: pp.ParserElement = kw['true'] | kw['false']
bool_lit.set_parse_action(lambda s, loc, toks: BoolLiteral(s, loc, toks[0] == 'true'))
result = kw['result'].set_parse_action(lambda s, loc, _: ResultExpr(s, loc))

assign = pp.Suppress(':=')
semi = pp.Suppress(';')
left_brace = pp.Suppress('{')
right_brace = pp.Suppress('}')
left_paren = pp.Suppress('(')
right_paren = pp.Suppress(')')

unary_op = pp.one_of('+ - !')
mul_op = pp.one_of('* / %')
add_op = pp.one_of('+ -')
cmp_op = pp.one_of('<= < >= > == !=')
and_op = pp.Literal('&&')
or_op = pp.Literal('||')
ternary_op = (pp.Literal('?'), pp.Literal(':'))

assoc_table = [
    (unary_op, 1, pp.OpAssoc.RIGHT, prefix_ctor),
    (mul_op, 2, pp.OpAssoc.LEFT, infix_ctor),
    (add_op, 2, pp.OpAssoc.LEFT, infix_ctor),
    (cmp_op, 2, pp.OpAssoc.LEFT, infix_ctor),
    (and_op, 2, pp.OpAssoc.LEFT, infix_ctor),
    (or_op, 2, pp.OpAssoc.LEFT, infix_ctor),
    (ternary_op, 3, pp.OpAssoc.RIGHT, ternary_ctor),
]
expr = pp.Forward()
args = left_paren - pp.Opt(pp.Group(pp.DelimitedList(expr), True), []) - right_paren
call = identifier - args
call.set_parse_action(lambda s, loc, toks: CallExpr(s, loc, *toks))
primary = int_lit | bool_lit | result | identifier + ~left_paren | call
expr <<= pp.infix_notation(primary, assoc_table)
expr.set_name('expression')

precondition = sup_kw['#pre'] - expr
postcondition = sup_kw['#post'] - expr
invariant = sup_kw['#invariant'] - expr
variant = sup_kw['#variant'] - expr

statement = pp.Forward()
assignment = identifier - assign - expr - semi
assignment.set_parse_action(lambda s, loc, toks: Assignment(s, loc, toks[0], toks[1]))
block = left_brace - pp.Group(statement[...], True) - right_brace
block.set_parse_action(lambda s, loc, toks: Block(s, loc, *toks))
ifelse = pp.Forward()
ifelse <<= sup_kw['if'] - expr - block - sup_kw['else'] - (ifelse | block)
ifelse.set_parse_action(lambda s, loc, toks: IfElse(s, loc, *toks))
while_ = pp.Opt(invariant, None) + pp.Opt(variant, None) + sup_kw['while'] - expr - block
while_.set_parse_action(lambda s, loc, toks: While(s, loc, *toks))
assert_ = sup_kw['assert'] - expr - semi
assert_.set_parse_action(lambda s, loc, toks: Assert(s, loc, *toks))
return_ = sup_kw['return'] - expr - semi
return_.set_parse_action(lambda s, loc, toks: Return(s, loc, *toks))
statement <<= ifelse | return_ | assert_ | assignment | while_

params = left_paren - pp.Opt(pp.Group(pp.DelimitedList(identifier), True), []) - right_paren

proc = pp.Opt(precondition, None) + pp.Opt(postcondition, None) + pp.Opt(variant, None) +\
    sup_kw['proc'] - identifier - params - block
proc.set_parse_action(lambda s, loc, toks: Proc(s, loc, *toks))
proc.set_name('proc')

fn = sup_kw['fn'] - identifier - params - assign - expr - semi
fn.set_parse_action(lambda s, loc, toks: Fn(s, loc, *toks))
fn.set_name('fn')

decls = proc | fn
program = decls[1, ...]
parser = program
parser.ignore(pp.dbl_slash_comment)
