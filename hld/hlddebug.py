#!/usr/bin/env python3

import hldast
import z3
import pyparsing

def hoare_assignment(post, assignment: hldast.Assignment):
    dest = hldast.expr_to_z3(assignment.dest)
    expr = hldast.expr_to_z3(assignment.expr)
    return z3.substitute(post, (dest, expr))

def hoare_ifelse(post, ifelse: hldast.IfElse):
    truthy = hoare_block(post, ifelse.truthy)
    falsey = hoare_block(post, ifelse.falsey)
    cond = hldast.expr_to_z3(ifelse.cond)
    return z3.And(z3.Implies(cond, truthy), z3.Implies(z3.Not(cond), falsey))

def hoare_block(post, block):
    assertion = post
    for st in reversed(block):
        ty = type(st)
        if ty == hldast.Assignment:
            assertion = hoare_assignment(assertion, st)
        elif ty == hldast.IfElse:
            assertion = hoare_ifelse(assertion, st)
        else:
            assert False, 'unimplemented'
    return assertion

def get_pre(proc: hldast.Proc):
    post = hldast.expr_to_z3(proc.post)
    assertion = hoare_block(post, proc.body)
    if proc.pre != None:
        s = z3.Solver()
        pre = hldast.expr_to_z3(proc.pre)
        s.add(z3.Not(z3.Implies(pre, assertion)))
        if s.check() != z3.unsat:
            print('precondition cannot hold')
    s = z3.Solver()
    s.add(assertion)
    if s.check() == z3.unsat:
        print('precondition found cannot hold')
    return z3.simplify(assertion, arith_lhs=True)
