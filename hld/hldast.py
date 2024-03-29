#!/usr/bin/env python3

import dataclasses
import pyparsing

from abc import ABC
from dataclasses import dataclass
from operator import attrgetter
from typing import Optional, NoReturn, Union

@dataclass(frozen=True, repr=False)
class ASTNode(ABC):
    src: str
    loc: int

    def error(self, msg: str) -> NoReturn:
        lineno = pyparsing.lineno(self.loc, self.src)
        col = pyparsing.col(self.loc, self.src)
        line = pyparsing.line(self.loc, self.src)
        ptr = f'{" " * (col-1)}^'
        raise HLDError(f'{lineno}:{col}: error: {msg}\n{line}\n{ptr}')

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
class TernaryExpr(Expr):
    cond: Expr
    then_expr: Expr
    else_expr: Expr

class ResultExpr(Expr):
    pass

@dataclass(frozen=True, repr=False)
class CallExpr(Expr):
    callee: Identifier
    args: list[Expr]

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
    else_block: Union[Block, 'IfElse']

@dataclass(frozen=True, repr=False)
class While(Statement):
    invariant: Optional[Expr]
    variant: Optional[Expr]
    cond: Expr
    body: Block

@dataclass(frozen=True, repr=False)
class Assert(Statement):
    expr: Expr

@dataclass(frozen=True, repr=False)
class Return(Statement):
    expr: Expr

@dataclass(frozen=True, repr=False)
class Proc(Declaration):
    pre: Optional[Expr]
    post: Optional[Expr]
    variant: Optional[Expr]
    name: Identifier
    params: list[Identifier]
    body: Block

@dataclass(frozen=True, repr=False)
class Fn(Declaration):
    name: Identifier
    params: list[Identifier]
    expr: Expr

class HLDError(RuntimeError):
    pass
