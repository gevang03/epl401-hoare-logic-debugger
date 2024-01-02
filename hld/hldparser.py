#!/usr/bin/env python3

import pyparsing as pp
from hldast import *

def infix_ctor(loc: int, tokens: pp.ParseResults):
    tokens, = tokens
    left = tokens[0]
    for i in range(len(tokens) // 2):
        op = tokens[2 * i + 1]
        left = Infix(loc, op, left, tokens[2 * i + 2])
    return left

def prefix_ctor(loc: int, tokens: pp.ParseResults):
    tokens, = tokens
    return Prefix(loc, tokens[0], tokens[1])

keywords = {'if', 'while', 'true', 'false', 'return'}

identifier = pp.Combine(pp.Opt('$') + pp.pyparsing_common.identifier)
identifier.add_condition(lambda s: s[0] not in keywords)
int_lit = pp.pyparsing_common.integer
bool_lit = pp.Keyword('true') | pp.Keyword('false')
bool_lit.set_parse_action(lambda s: s[0] == 'true')

assign = pp.Suppress(':=')
semi = pp.Suppress(';')
left_brace = pp.Suppress('{')
right_brace = pp.Suppress('}')

unary_op = pp.one_of('+ - !')
mul_op = pp.Literal('*')
add_op = pp.one_of('+ -')
cmp_op = pp.one_of('<= < >= > == !=')
and_op = pp.Literal('&&')
or_op = pp.Literal('||')

keyword_if = pp.Suppress(pp.Keyword('if'))
keyword_else = pp.Suppress(pp.Keyword('else'))
keyword_while = pp.Suppress(pp.Keyword('while'))

keyword_pre = pp.Suppress(pp.Keyword('#pre'))
keyword_post = pp.Suppress(pp.Keyword('#post'))
keyword_invariant = pp.Suppress(pp.Keyword('#invariant'))
keyword_variant = pp.Suppress(pp.Keyword('#variant'))
keyword_proc = pp.Suppress(pp.Keyword('proc'))

assoc_table = [
    (unary_op, 1, pp.OpAssoc.RIGHT, prefix_ctor),
    (mul_op, 2, pp.OpAssoc.LEFT, infix_ctor),
    (add_op, 2, pp.OpAssoc.LEFT, infix_ctor),
    (cmp_op, 2, pp.OpAssoc.LEFT, infix_ctor),
    (and_op, 2, pp.OpAssoc.LEFT, infix_ctor),
    (or_op, 2, pp.OpAssoc.LEFT, infix_ctor),
]
expr = pp.infix_notation(int_lit | bool_lit | identifier, assoc_table)

precondition = keyword_pre + expr
postcondition = keyword_post + expr
invariant = keyword_invariant + expr
variant = keyword_variant + expr

statement = pp.Forward()
assignment = identifier + assign + expr + semi
assignment.set_parse_action(lambda loc, tokens: Assignment(loc, tokens[0], tokens[1]))
block = left_brace + pp.Group(statement[...], True) + right_brace
if_statement = pp.Forward()
if_statement <<= keyword_if + expr + block + keyword_else + (if_statement | block)
if_statement.set_parse_action(lambda loc, tokens: IfElse(loc, *tokens))
while_statement = pp.Opt(invariant, None) + pp.Opt(variant, None) + keyword_while + expr + block
while_statement.set_parse_action(lambda loc, tokens: While(loc, *tokens))
statement <<= if_statement | while_statement | assignment

params = pp.Suppress('(') + pp.Group(pp.DelimitedList(identifier)) + pp.Suppress(')')

proc = pp.Opt(precondition, None) + pp.Opt(postcondition, None) + keyword_proc + identifier + params + block

parser = proc.ignore(pp.dbl_slash_comment)
print(parser.parse_string(
'''
#pre x > $x0
#post 1 == 3
proc foo(x, y) {
    #invariant true
    #variant x - 1
    while x - 1 {
        foo := -1;
        // comment
        bar := 2;
    }
}
'''))
