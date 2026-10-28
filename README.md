# Mini Compiler for Arithmetic Expressions

A small but complete compiler, written from scratch with no external libraries. It turns an arithmetic expression such as `2 + 3 * 4` into stack-machine bytecode and runs it on a virtual machine. A web interface shows every stage live.

## Pipeline

```
Source text -> Lexer -> Tokens -> Parser -> AST
            -> Optimizer (constant folding) -> Code generator
            -> Stack bytecode -> Virtual machine -> Result
```

| Stage | What it does |
|---|---|
| Lexer | Splits the text into tokens (`NUM`, `PLUS`, `STAR`, ...) |
| Parser | Recursive-descent parser that builds an abstract syntax tree (AST) |
| Optimizer | Constant folding: evaluates constant sub-trees at compile time |
| Code generator | Post-order walk of the tree that emits stack instructions |
| Virtual machine | Fetch-decode-execute loop over a stack |

## Features

- Operators: `+  -  *  /  %  ^` (power), unary minus, parentheses
- Integers and decimals
- Correct precedence and associativity (`^` is right-associative, so `2 ^ 3 ^ 2 = 512`)
- Error messages with a caret under the exact mistake
- Division-by-zero detection at compile time (with folding) and run time
- Web interface with token chips, syntax-tree drawing, bytecode table and a step-by-step stack visualiser

## Grammar

```
expr  -> term  (('+' | '-') term)*
term  -> unary (('*' | '/' | '%') unary)*
unary -> '-' unary | power
power -> atom ('^' unary)?        right-associative
atom  -> NUMBER | '(' expr ')'
```

Each rule is one method of the `Parser` class. Rules lower in the list bind tighter, which is how precedence is achieved without a precedence table.

## Getting started

Requires Python 3.8 or newer. No packages to install.

```bash
git clone https://github.com/<your-username>/mini-compiler.git
cd mini-compiler
```

### Command line

```bash
python mini_compiler.py                      # interactive REPL
python mini_compiler.py "2 + 3 * 4"          # one-shot, prints 14
python mini_compiler.py --debug "2+3*(4-1)"  # show tokens, AST, bytecode
```

Inside the REPL, prefix an expression with `:d ` to see all stages, and type `quit` to exit.

### Web interface

Open `index.html` in any browser (double-click it). Nothing to install or build.

### Tests

```bash
python -m unittest discover -s tests -v
```

## Example

```
$ python mini_compiler.py --debug "2 + 3 * (4 - 1)"
TOKENS: [('NUM', 2), ('PLUS', '+'), ('NUM', 3), ('STAR', '*'), ('LPAREN', '('), ('NUM', 4), ('MINUS', '-'), ('NUM', 1), ('RPAREN', ')')]
AST:
Bin(+)
  Num(2)
  Bin(*)
    Num(3)
    Bin(-)
      Num(4)
      Num(1)
AST after constant folding:
Num(11)
BYTECODE:
  00  PUSH  11
11
```

Error reporting:

```
$ python mini_compiler.py "2 + * 3"
Error: Unexpected '*'
  2 + * 3
      ^
```

## Project structure

```
mini-compiler/
├── mini_compiler.py     # lexer, parser, optimizer, code generator, VM, CLI
├── index.html           # web interface (same pipeline in JavaScript)
├── tests/
│   └── test_compiler.py # unit tests
├── README.md
├── LICENSE
└── .gitignore
```

## How it works (short version)

1. **Lexing.** A single left-to-right scan groups characters into tokens. Numbers use "maximal munch": keep consuming digits and dots.
2. **Parsing.** Recursive descent with one token of lookahead (LL(1)). Loops in `expr` and `term` give left associativity. Recursing on the right side in `power` gives right associativity.
3. **Optimizing.** `fold()` visits children first and replaces any operator whose operands are both numbers with the computed result.
4. **Code generation.** Emitting the left child, then the right child, then the operator produces postfix order, for example `2 3 4 * +`.
5. **Execution.** The VM pushes numbers and, for each operator, pops the right operand first, then the left, and pushes the result.

## Limitations

- Very deep nesting can hit Python's recursion limit
- Huge powers such as `9 ^ 9 ^ 9` can exhaust memory
- No variables, functions or statements yet
- Errors found after parsing (such as division by zero) do not carry a source position

## Future scope

- Variables and assignment with `LOAD` / `STORE` instructions
- Built-in functions (`sqrt`, `max`, `abs`)
- Comparison and logical operators
- Source positions stored in every AST node
- Saving and loading compiled bytecode
- Emitting real assembly or LLVM IR

## License

MIT. See [LICENSE](LICENSE).
