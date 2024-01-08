#!/usr/bin/env python3

from collections import namedtuple
import functools
import operator
import z3

Prefix = namedtuple('Prefix', ['loc', 'op', 'expr'])
Infix = namedtuple('Infix', ['loc', 'op', 'left', 'right'])

Assignment = namedtuple('Assignment', ['loc', 'dest', 'expr'])
IfElse = namedtuple('IfElse', ['loc', 'cond', 'truthy', 'falsey'])
While = namedtuple('While', ['loc', 'invariant', 'variant', 'cond', 'body'])
Proc = namedtuple('Proc', ['loc', 'pre', 'post', 'name', 'params', 'body'])

__ops = {
  '*': operator.mul,
  '+': operator.add,
  '-': operator.sub,
  '<=': operator.le,
  '<': operator.lt,
  '>=': operator.ge,
  '>': operator.gt,
  '==': operator.eq,
  '!=': operator.ne,
  '&&': z3.And,
  '||': z3.Or,
}

def __infix_to_z3(inf: Infix):
    left = expr_to_z3(inf.left)
    right = expr_to_z3(inf.right)
    return __ops[inf.op](left, right)

def __prefix_to_z3(pref: Prefix):
    expr = expr_to_z3(pref.expr)
    if pref.op == '!':
        return z3.Not(expr)
    if pref.op == '-':
        return -expr
    if pref.op == '+':
        return +expr
    assert False, 'unreachable'

@functools.cache
def expr_to_z3(expr):
    ty = type(expr)
    if ty == bool:
        return z3.BoolVal(expr)
    if ty == int:
        return z3.IntVal(expr)
    if ty == str:
        return z3.Int(expr)
    if ty == Prefix:
        return __prefix_to_z3(expr)
    if ty == Infix:
        return __infix_to_z3(expr)
    assert False, 'unreachable'
