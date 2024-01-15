#!/usr/bin/env python3

import dataclasses
import operator
import pyparsing
import z3

from abc import ABC
from dataclasses import dataclass
from operator import attrgetter
from functools import cache, singledispatch

@dataclass(frozen=True, repr=False)
class ASTNode(ABC):
    src: str
    loc: int

    def message(self, type: str, msg: str) -> str:
        lineno = pyparsing.lineno(self.loc, self.src)
        col = pyparsing.lineno(self.loc, self.src)
        return f'<filename>: {lineno}:{col}: {type}: {msg}'

    def error(self, msg: str) -> str:
        return self.message('error', msg)

    def __repr__(self) -> str:
        pairs = (((f.name, attrgetter(f.name)(self))
                  for f in dataclasses.fields(self)
                    if not f.name in {'src', 'loc'}
                  ))
        as_str = ', '.join(f'{k}={repr(v)}' for k, v in pairs)
        return f'{self.__class__.__name__}({as_str})'

class Declaration(ASTNode, ABC):
    pass

class Statement(ASTNode, ABC):
    pass

class Expr(ASTNode, ABC):
    pass

class Literal(Expr, ABC):
    pass

@dataclass(frozen=True, repr=False)
class Identifier(Expr):
    value: str

@dataclass(frozen=True, repr=False)
class BoolLiteral(Literal):
    value: bool

@dataclass(frozen=True, repr=False)
class IntLiteral(Literal):
    value: int

@dataclass(frozen=True, repr=False)
class PrefixExpr(Expr, ABC):
    op: str
    expr: Expr

class PrefixArithmeticExpr(PrefixExpr):
    pass

class PrefixLogicalExpr(PrefixExpr):
    pass

@dataclass(frozen=True, repr=False)
class InfixExpr(Expr, ABC):
    op: str
    left: Expr
    right: Expr

class InfixArithmeticExpr(InfixExpr):
    pass

class InfixLogicalExpr(InfixExpr):
    pass

class InfixRelationalExpr(InfixExpr):
    pass

@dataclass(frozen=True, repr=False)
class Assignment(Statement):
    dest: Identifier
    value: Expr

@dataclass(frozen=True, repr=False)
class Block(Statement):
    statements: list[Statement]

@dataclass(frozen=True, repr=False)
class IfElse(Statement):
    cond: Expr
    then_block: Block
    else_block: Block

@dataclass(frozen=True, repr=False)
class While(Statement):
    invariant: Expr | None
    variant: Expr | None
    cond: Expr
    body: Block

@dataclass(frozen=True, repr=False)
class Proc(Declaration):
    pre: Expr | None
    post: Expr | None
    name: Identifier
    params: list[Identifier]
    body: Block

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

@expr_to_z3.register
def _(expr: InfixArithmeticExpr) -> z3.ArithRef:
    left = expr_to_z3(expr.left)
    assert isinstance(left, z3.ArithRef)
    right = expr_to_z3(expr.right)
    assert isinstance(right, z3.ArithRef)
    ops = { '*': operator.mul, '+': operator.add, '-': operator.sub }
    res = ops[expr.op](left, right)
    assert isinstance(res, z3.ArithRef)
    return res

@expr_to_z3.register
def _(expr: InfixLogicalExpr) -> z3.BoolRef:
    left = expr_to_z3(expr.left)
    assert isinstance(left, z3.BoolRef)
    right = expr_to_z3(expr.right)
    assert isinstance(right, z3.BoolRef)
    ops = { '&&': z3.And, '||': z3.Or }
    res = ops[expr.op](left, right)
    assert isinstance(res, z3.BoolRef)
    return res

@expr_to_z3.register
def _(expr: InfixRelationalExpr) -> z3.BoolRef:
    left = expr_to_z3(expr.left)
    assert isinstance(left, z3.ArithRef)
    right = expr_to_z3(expr.right)
    assert isinstance(right, z3.ArithRef)
    ops = { 
        '<=': operator.le, '<': operator.lt,
        '>=': operator.ge, '>': operator.gt,
        '==': operator.eq, '!=': operator.ne
    }
    res = ops[expr.op](left, right)
    assert isinstance(res, z3.BoolRef)
    return res
