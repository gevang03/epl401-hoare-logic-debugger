# Hoare Logic Debugger

## Usage
```sh
$ ./hld/run.py [OPTIONS] FILE
```

> Run `./hld/run.py -h` for help.

## Tests
```sh
$ python3 -m unittest discover -s hld -v
```

## Syntax
Using [EBNF Notation](https://www.iso.org/standard/26153.html).
Whitespace is not significant and ommited for brevity.

```ebnf
program = procedure;

procedure = [pre], [post], 'proc', identifier, paramlist, block;

(* STATEMENTS *)
statement = ifelse | assert | assignment | while;
ifelse = 'if', expression, block, 'else', block;
assert = 'assert', expression, ';';
assignment = identifier, '::=', expression, ';';
while = [invariant], [variant], 'while', expression, block;
block = '{', {statement}, '}';

(* EXPRESSIONS *)
expression = primary | ternary_expr;

(* Using regex: /\$?[a-zA-Z_][a-zA-Z0-9_]*/ *)
identifier = ['$'], (alpha | '_'), {alphanum | '_'};
literal = bool | int;
bool = 'true' | 'false';
int = digits, {digits};

(* ASSERTIONS *)
pre = '#pre', expression;
post = '#post', expression;
invariant = '#invariant', expression;
variant = '#variant', expression;

(* AUXILIARY *)
paramlist = '(', [identifier, {',', identifier}], ')';

alphanum = alpha | digits;
alpha = lower | upper;
lower = ? letters a to z ?;
upper = ? letters A to Z ?;
digits = ? digits 0 to 9 ?;

ternary_expr = or_expr, '?', ternary_expr, ':', ternary_expr;
or_expr = and_expr, '||', and_expr;
and_expr = rel_expr, '&&', rel_expr;
rel_expr = add_expr, rel_op, add_expr;
add_expr = mul_expr, add_op, mul_expr;
mul_expr = unary_expr, mul_op, unary_expr;
unary_expr = un_op, primary;
primary = '(' expression ')' | literal | identifier;

rel_op = '<' | '<=' | '==' | '!=' | '>=' | '>';
add_op = '+' | '-';
mul_op = '*';
un_op = '+' | '-' | '!';
```

## Language Semantics
The language semantics are based on a simply typed variant of the WHILE language.

Identifiers prefixed with dollar ($) are symbolic and may appear in precondition, postcondition, variants and invariants.
Symbolic variables and procedure parameters are always assume to be integer typed.

## Hoare Logic Semantics

### Assignment Rule
$$
\{\phi [E/x]\}\; x:=E\; \{\phi\}
$$

### Consequence Rule
$$
\frac
{
    \phi \to \phi_0 \quad
    \{\phi_0\}\; C\; \{\psi_0\}\quad
    \psi_0 \to \psi
}
{
    \{\phi\}\; C\; \{\psi\}
}
$$

### Composition Rule
$$
\frac
{
    \{\phi\}\; C_1\; \{\eta\}\quad
    \{\eta\}\; C_2\; \{\psi\}\;
}
{
    \{\phi\}\; C_1; C_2\{\psi\}
}
$$

### If Rule
$$
\frac
{
    \{\phi \land B\}\; C_1\; \{\psi\}\quad
    \{\phi \land \neg B\}\; C_2\; \{\psi\}
}
{
    \{\phi\} \texttt{if}\; B\; \texttt{then}\; C_1\; \texttt{else}\; C_2\; \{\psi\}
}
$$

### Partial While Rule
$$
\frac
{
    \{\eta \land B\}\; C\; \{\eta\}
}
{
    \{\eta\}\; \texttt{while}\; B\; C\; \{\eta \land \neg B\}
}
$$

### Total While Rule
$$
\frac
{
    \{\eta \land B \land 0 \le E = E_0\}\; C\; \{\eta \land 0 \le E \lt E_0 \}
}
{
    \{\eta \land 0 \le E\}\; \texttt{while}\; B\; C\; \{\eta \land \neg B\}
}
$$

### Assert Rule
$$
\frac
{
    \phi \to \psi
}
{
    \{\phi\}\; \texttt{assert}\; \psi \{\phi\}
}
$$

### Function Call Rule
$$
\frac
{
    \{\phi\}\; \texttt{proc} f(x_1, ..., x_n)\; B\; \{\psi\}\quad
    \phi[a_i/x_i]
}
{
    \{\phi[a_i/x_i]\}\; f(a_1, ..., a_n)\; \{\psi[a_i/x_i]\}
}
$$
