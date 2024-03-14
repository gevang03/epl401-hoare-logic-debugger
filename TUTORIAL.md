# Hoare Logic Debugger (HLD) Tutorial

## Introduction
The purpose of this tool is to assist in finding bugs in programs, thus making programming easier.
The tool uses formal methods to detect bugs and verify correctness and termination.

## Build

You can build this tool at the b103 lab.
On linux, run the following commands. Make sure that `python3 --version` is >= 3.9.18

```bash
$ git clone --depth=1 https://github.com/gevang03/epl401-hoare-logic-debugger.git
$ cd epl401-hoare-logic-debugger
$ python3 -m venv .venv
$ . .venv/bin/activate
$ pip install --require-virtualenv -r requirements.txt
```

## Usage
```sh
$ ./hld/run.py [OPTIONS] FILE
```

> Run `./hld/run.py FILE` to check for partial correctness

> Run `./hld/run.py --total FILE` to check for total 
correctness (termination)

> Run `./hld/run.py --run 'f x y' FILE` to execute procedure f with arguments x and y.

> Run `./hld/run.py -h` for help.

## Language
The HLD language that the tool supports is procedural and should be familiar to any c/java programmmer.
There also exist some constructs to express program specifications.

### Types and Basic Expressions
Only two value types exist in HLD:
* booleans (`true`, `false`)
* signed integers (represented in base 10)

The following prefix/infix operators are defined with the same meaning, precedence and associativity as in [c or java](https://en.cppreference.com/w/c/language/operator_precedence):

* Arithmetic: `+, -, *, /, %`
* Boolean: `!, &&, ||`
* Relational: `<, <=, ==, !=, >=, >`
* Conditional: `?:`

Parenthesis `()` can be used to group expressions.
Relational operators are defined for integer typed expressions only.

### Variables
Variables can be declared/assigned:
```rs
// c++ style comments
x := 11;
p := false;
y := x + 3;
```

The division and modulo operator cannot be nested in expressions, they must be directly assigned to a variable.

Example:
```rs
temp := x / y;
a := temp + 1;
// `a := (x / y) + 1;` is illegal
```

### Control Flow
The following control flow structures are available:

if-else statements:
```rs
if x < 1 { // note that braces {} are mandatory.
    y := 3;
} else {
    y := x + 1;
}
```

while loops:
Note: while loop conditions are referred as guards by the tool.
```rs
while x < 10 {
    s := s + x;
    x := x + 1;
}
```

return statements:
```rs
proc foo() {
    // ...
    return -1;
}
```

assert statements: must be supplied a boolean condition which should evaluate to true for every valid execution of a program.
```rs
assert x > 0;
```

### Procedures
Procedures are the basic abstraction used to define specifications and discover bugs in a program.

* Procedures accept a number of integer parameters and return a single integer value.
Parameters cannot be reassigned (they are immutable).

* Procedures must end with a return statement in a every reaching path of execution.

* Procedures may be preceeded by a precondition (a condition which should hold before the execution of the procedure).

* Procedures may be preceeded by a postcondition (a condition which should hold after the execution of the procedure).
The result keyword is used to represent the value returned by the procedure

Example:
```rs
#pre x >= 0           // precondition
#post result == x + 1 // postcondition
proc inc(x) {
    y := x + 1;
    return y;
}
```

#### Procedure Calls
Procedures may be called with the required number of arguments.
However they must be immediately assigned, not nested in any other expressions.

Example:
```rs
#pre x >= 0
#post result == x + 2
proc inc2(x) {
    x1 := inc(x);
    x2 := inc(x1);
    // `return inc(inc(x));` is illegal
    return x2;
}
```

### Variants and Invariants
Invariants are conditions which should hold before during and after the execution of an iteration of
a while loop/recursive call. They are used to prove the correctness of these iterative structures.

Variants are integer expressions which each iteration must be decreased and are always bound by zero.
They are used to prove termination of while loops/recursive calls.

Example:
```rs
#pre n >= 0
#post result = n * (n - 1) / 2
proc sum(n) {
    i := 0;
    total := 0;
    #invariant total == i * (i - 1) / 2
    #variant n - i
    while i != y {
        total := total + i;
        i := i + 1;
    }
    return total;
}
```

### Functions
Functions are used to define other specifications, that may require recursion to do so, for example.
Their body consists of a single expression. Functions cannot be called inside of a procedure.

```rs
// 'equivalent' to:
// function fct(n) {
//     if (n <= 0) {
//         return 1;
//     } else {
//         return n * fct(n - 1);
//     }
// }
fn fct(n) := n <= 0 ? 1 : n * fct(n - 1);

// note that variant here is used to prove the termination of a recursive procedure
#pre x >= 0
#post result == fct(x)
#variant x
proc calc_fct(x) {
  if x == 0 {
    return 1;
  } else {
    y := calc_fct(x-1);
    return x * y;
  }
}
```

## Some tips on using the HLD tool
* Attempt to verify partial correctness before total correctness, to avoid cluttered results that may be unhelpful.
* Assertions might help in pinpointing what exactly is wrong.
* Executing the program can give empirical results (wrong values, non-termination) that may indicate
if there is something wrong with your code or with any of the specified metaconditions (variants, invariants, etc.).
* The tool may provide some counter examples that can be used to verify what is wrong.
