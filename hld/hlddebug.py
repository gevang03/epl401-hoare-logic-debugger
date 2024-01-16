#!/usr/bin/env python3

import operator
import z3
from functools import singledispatch, cache
from hldast import *

@singledispatch
@cache
def expr_to_z3(_: Expr) -> z3.BoolRef | z3.ArithRef:
    raise NotImplementedError

@expr_to_z3.register
def _(expr: BoolLiteral) -> z3.BoolRef:
    return z3.BoolVal(expr.value)

@expr_to_z3.register
def _(expr: IntLiteral) -> z3.IntNumRef:
    return z3.IntVal(expr.value)

@expr_to_z3.register
def _(expr: Identifier) -> z3.ArithRef:
    return z3.Int(expr.value)

@expr_to_z3.register
def _(pref: PrefixArithmeticExpr) -> z3.ArithRef:
    expr = expr_to_z3(pref.expr)
    assert isinstance(expr, z3.ArithRef)
    if pref.op == '+':
        return +expr
    else:
        assert pref.op == '-'
        return -expr

@expr_to_z3.register
def _(pref: PrefixLogicalExpr) -> z3.BoolRef:
    expr = expr_to_z3(pref.expr)
    assert isinstance(expr, z3.BoolRef)
    assert pref.op == '!'
    res = z3.Not(expr)
    assert isinstance(res, z3.BoolRef)
    return res

_infix_arith_ops = { '*': operator.mul, '+': operator.add, '-': operator.sub }

@expr_to_z3.register
def _(expr: InfixArithmeticExpr) -> z3.ArithRef:
    left = expr_to_z3(expr.left)
    assert isinstance(left, z3.ArithRef)
    right = expr_to_z3(expr.right)
    assert isinstance(right, z3.ArithRef)
    res = _infix_arith_ops[expr.op](left, right)
    assert isinstance(res, z3.ArithRef)
    return res

_infix_logical_ops = { '&&': z3.And, '||': z3.Or }

@expr_to_z3.register
def _(expr: InfixLogicalExpr) -> z3.BoolRef:
    left = expr_to_z3(expr.left)
    assert isinstance(left, z3.BoolRef)
    right = expr_to_z3(expr.right)
    assert isinstance(right, z3.BoolRef)
    res = _infix_logical_ops[expr.op](left, right)
    assert isinstance(res, z3.BoolRef)
    return res

_infix_rel_ops = { 
    '<=': operator.le, '<': operator.lt,
    '>=': operator.ge, '>': operator.gt,
    '==': operator.eq, '!=': operator.ne
}

@expr_to_z3.register
def _(expr: InfixRelationalExpr) -> z3.BoolRef:
    left = expr_to_z3(expr.left)
    assert isinstance(left, z3.ArithRef)
    right = expr_to_z3(expr.right)
    assert isinstance(right, z3.ArithRef)
    res = _infix_rel_ops[expr.op](left, right)
    assert isinstance(res, z3.BoolRef)
    return res

@singledispatch
def hoare_propagate(_: Statement, _post: z3.BoolRef) -> z3.BoolRef:
    raise NotImplementedError

@hoare_propagate.register
def _(assignment: Assignment, post: z3.BoolRef) -> z3.BoolRef:
    dest = expr_to_z3(assignment.dest)
    value = expr_to_z3(assignment.value)
    res = z3.substitute(post, (dest, value))
    assert isinstance(res, z3.BoolRef)
    return res

@hoare_propagate.register
def _(ifelse: IfElse, post: z3.BoolRef) -> z3.BoolRef:
    then_block = hoare_propagate(ifelse.then_block, post)
    else_block = hoare_propagate(ifelse.else_block, post)
    cond = expr_to_z3(ifelse.cond)
    res = z3.And(z3.Implies(cond, then_block), z3.Implies(z3.Not(cond), else_block))
    assert isinstance(res, z3.BoolRef)
    return res

@hoare_propagate.register
def _(block: Block, post: z3.BoolRef) -> z3.BoolRef:
    assertion = post
    for statement in reversed(block.statements):
        assertion = hoare_propagate(statement, assertion)
    return assertion

def get_pre(proc: Proc):
    post = expr_to_z3(proc.post)
    assertion = hoare_propagate(proc.body, post)
    if proc.pre != None:
        s = z3.Solver()
        pre = expr_to_z3(proc.pre)
        s.add(z3.Not(z3.Implies(pre, assertion)))
        if s.check() != z3.unsat:
            print('precondition cannot hold')
    s = z3.Solver()
    s.add(assertion)
    if s.check() == z3.unsat:
        print('precondition found cannot hold')
    return z3.simplify(assertion, arith_lhs=True)
