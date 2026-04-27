from typing import List, Optional

from .tokens import Token, TokenType, KEYWORDS
from .lexer import simple_lex
from .error_handler import ErrorHandler

class Node:
    def __init__(self, name: str):
        self.name = name
        self.children = []

    def add_child(self, node: 'Node') -> 'Node':
        if node:
            self.children.append(node)
        return self


class ParseError:
    def __init__(self, message: str, line: int, column: int):
        self.message = message
        self.line = line
        self.column = column

    def __repr__(self) -> str:
        return f"ParseError({self.message!r}, line={self.line}, column={self.column})"


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.index = 0
        self.errors: List[ParseError] = []
        self.corrected_tokens: List[Token] = []
        self.error_handler = ErrorHandler(self)
        self.symbol_table: set[str] = set()  # Track declared variables

    # Public API
    def parse(self) -> 'Node':
        return self.program()

    def get_errors(self) -> List[ParseError]:
        return self.errors

    def get_corrected_source(self) -> str:
        parts: List[str] = []
        prev = None
        for t in self.corrected_tokens:
            # simple spacing rules: add space between identifiers/numbers/keywords
            if prev and (prev.type in (TokenType.IDENTIFIER, TokenType.NUMBER, TokenType.KEYWORD) and
                         t.type in (TokenType.IDENTIFIER, TokenType.NUMBER, TokenType.KEYWORD)):
                parts.append(" ")
            parts.append(t.to_source())
            prev = t
        return "".join(parts)

    # ---- Parser utilities ----
    def current(self) -> Token:
        return self.tokens[self.index]

    def advance(self) -> Token:
        tok = self.current()
        self.index = min(self.index + 1, len(self.tokens) - 1)
        # append consumed token to corrected stream
        self.corrected_tokens.append(tok)
        return tok

    def consume_without_append(self) -> Token:
        tok = self.current()
        self.index = min(self.index + 1, len(self.tokens) - 1)
        return tok

    def insert_token(self, lexeme: str, ttype: TokenType, line: int, column: int) -> Token:
        return self.error_handler.insert(lexeme, ttype, line, column)

    def add_error(self, message: str, token: Optional[Token] = None) -> None:
        self.error_handler.record_error(message, token)

    def panic_mode(self) -> None:
        # Delegate panic-mode skipping to the error handler
        self.error_handler.panic()


    def expect_exact(self, lexeme: str, token_type: TokenType, node: 'Node', custom_error: Optional[str] = None) -> None:
        if self.current().lexeme == lexeme:
            self.advance()
            node.add_child(Node(lexeme))
        else:
            if custom_error:
                self.add_error(custom_error, self.current())
            self.insert_token(lexeme, token_type, self.current().line, self.current().column)
            node.add_child(Node(lexeme))

    # ---- Grammar rules (one method per production) ----
    def program(self) -> 'Node':
        root = Node("Program")
        root.add_child(self.stmt_list())
        
        # expect EOF
        if self.current().type != TokenType.EOF:
            self.add_error("Expected EOF")
            
        return root

    def stmt_list(self) -> 'Node':
        node = Node("StmtList")
        tok = self.current()
        if tok.type == TokenType.EOF or tok.lexeme == '}':
            node.add_child(Node("ε"))
            return node
            
        node.add_child(self.stmt())
            
        node.add_child(self.stmt_list())
        return node

    def stmt(self) -> Optional['Node']:
        node = Node("Stmt")
        tok = self.current()
        if tok.type == TokenType.KEYWORD and tok.lexeme in ('int', 'float'):
            node.add_child(self.declaration())
        elif tok.type == TokenType.IDENTIFIER:
            node.add_child(self.assignment())
        elif tok.type == TokenType.KEYWORD and tok.lexeme == 'if':
            node.add_child(self.if_stmt())
        elif tok.type == TokenType.KEYWORD and tok.lexeme == 'while':
            node.add_child(self.while_stmt())
        else:
            self.add_error("Unexpected token at start of statement", tok)
            self.panic_mode()
            return None
        return node

    def declaration(self) -> 'Node':
        node = Node("Declaration")
        # type
        t = self.current()
        self.advance()
        node.add_child(Node(t.lexeme))
        # identifier
        if self.current().type == TokenType.IDENTIFIER:
            id_tok = self.current()
            self.advance()
            node.add_child(Node(id_tok.lexeme))
            # Add to symbol table
            self.symbol_table.add(id_tok.lexeme)
        else:
            # insert dummy identifier
            id_tok = self.insert_token('id_missing', TokenType.IDENTIFIER, t.line, t.column)
            node.add_child(Node(id_tok.lexeme))

        # optional initialization: = expression
        if self.current().lexeme == '=':
            self.advance()
            node.add_child(Node("="))
            node.add_child(self.expr())

        # semicolon
        self.expect_exact(';', TokenType.DELIMITER, node)
            
        return node

    def assignment(self) -> 'Node':
        node = Node("Assignment")
        # id
        id_tok = self.current()
        self.advance()  # consume the identifier
        node.add_child(Node(id_tok.lexeme))
        
        # Check if variable is declared
        if id_tok.lexeme not in self.symbol_table:
            self.add_error(f"Undeclared variable '{id_tok.lexeme}'", id_tok)
        
        # expect '='
        self.expect_exact('=', TokenType.OPERATOR, node, "Expected '=' after identifier in assignment")

        # expression
        node.add_child(self.expr())

        # semicolon
        self.expect_exact(';', TokenType.DELIMITER, node)

        return node

    def if_stmt(self) -> 'Node':
        node = Node("IfStmt")
        self.advance()  # consume 'if'
        node.add_child(Node("if"))
        
        # expect '('
        self.expect_exact('(', TokenType.DELIMITER, node)

        node.add_child(self.condition())

        self.expect_exact(')', TokenType.DELIMITER, node)

        # expect '{'
        self.expect_exact('{', TokenType.DELIMITER, node)

        node.add_child(self.stmt_list())

        self.expect_exact('}', TokenType.DELIMITER, node)
            
        return node

    def while_stmt(self) -> 'Node':
        node = Node("WhileStmt")
        self.advance()  # consume 'while'
        node.add_child(Node("while"))
        
        self.expect_exact('(', TokenType.DELIMITER, node)

        node.add_child(self.condition())

        self.expect_exact(')', TokenType.DELIMITER, node)

        self.expect_exact('{', TokenType.DELIMITER, node)

        node.add_child(self.stmt_list())

        self.expect_exact('}', TokenType.DELIMITER, node)

        return node

    def condition(self) -> 'Node':
        node = Node("Condition")
        # expr relop expr
        node.add_child(self.expr())
            
        # relop
        if self.current().type == TokenType.OPERATOR and self.current().lexeme in (
            '>', '<', '>=', '<=', '==', '!='
        ):
            op = self.current().lexeme
            self.advance()
            node.add_child(Node(op))
        else:
            # insert '==' as safe default
            self.insert_token('==', TokenType.OPERATOR, self.current().line, self.current().column)
            node.add_child(Node("=="))
            
        node.add_child(self.expr())
            
        return node

    # Expression rules
    def expr(self) -> 'Node':
        node = Node("Expr")
        node.add_child(self.term())
        expr_prime_node = self.expr_prime()
        node.add_child(expr_prime_node)
        return node

    def expr_prime(self) -> 'Node':
        node = Node("ExprPrime")
        if self.current().lexeme in ('+', '-'):
            op = self.current().lexeme
            self.advance()
            node.add_child(Node(op))
            node.add_child(self.term())
            node.add_child(self.expr_prime())
        else:
            node.add_child(Node("ε"))
        return node

    def term(self) -> 'Node':
        node = Node("Term")
        node.add_child(self.factor())
        term_prime_node = self.term_prime()
        node.add_child(term_prime_node)
        return node

    def term_prime(self) -> 'Node':
        node = Node("TermPrime")
        if self.current().lexeme in ('*', '/'):
            op = self.current().lexeme
            self.advance()
            node.add_child(Node(op))
            node.add_child(self.factor())
            node.add_child(self.term_prime())
        else:
            node.add_child(Node("ε"))
        return node

    def factor(self) -> 'Node':
        node = Node("Factor")
        tok = self.current()
        if tok.type == TokenType.IDENTIFIER:
            # Check if variable is declared
            if tok.lexeme not in self.symbol_table:
                self.add_error(f"Undeclared variable '{tok.lexeme}'", tok)
            self.advance()
            node.add_child(Node(tok.lexeme))
            return node
        elif tok.type == TokenType.NUMBER:
            self.advance()
            node.add_child(Node(tok.lexeme))
            return node
        if tok.lexeme == '(':
            self.advance()
            node.add_child(Node("("))
            node.add_child(self.expr())
            self.expect_exact(')', TokenType.DELIMITER, node)
            return node

        # Missing operand: insert default number 0
        self.insert_token('0', TokenType.NUMBER, tok.line, tok.column)
        node.add_child(Node("0"))
        return node


if __name__ == "__main__":
    sample = """
    int a
    a = 5 + ;
    if (a > ) { a = a - 1;
    """
    toks, lerrs = simple_lex(sample)
    p = Parser(toks)
    p.parse()
    print("Lexer errors:")
    for e in lerrs:
        print(e)
    print("Parser errors:")
    for e in p.get_errors():
        print(e)
    print("Corrected source:")
    print(p.get_corrected_source())
