from typing import List, Tuple
from dataclasses import dataclass

from .tokens import Token, TokenType, KEYWORDS, OPERATORS, DELIMITERS


@dataclass
class LexError:
    message: str
    line: int
    column: int


class Lexer:
    def __init__(self) -> None:
        self.source = ""
        self.length = 0
        self.index = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []
        self.errors: List[LexError] = []

    # ---- Public API ----
    def tokenize(self, source: str) -> Tuple[List[Token], List[LexError]]:
        """Tokenize `source` and return (tokens, errors).

        An EOF token is appended at the end.
        """
        self.source = source
        self.length = len(source)
        self.index = 0
        self.line = 1
        self.column = 1
        self.tokens = []
        self.errors = []

        while not self._is_at_end():
            ch = self._peek()
            if ch.isspace():
                self._consume_whitespace()
                continue
            start_line, start_col = self.line, self.column

            # Identifier or keyword
            if self._is_alpha(ch) or ch == "_":
                lex = self._consume_identifier()
                ttype = TokenType.KEYWORD if lex in KEYWORDS else TokenType.IDENTIFIER
                self.tokens.append(Token(ttype, lex, start_line, start_col))
                continue

            # Number (integer or float)
            if ch.isdigit():
                lex = self._consume_number()
                # If the number contains letters (malformed), report error and mark UNKNOWN
                if any(c.isalpha() for c in lex):
                    self._add_error("Invalid number literal", start_line, start_col)
                    self.tokens.append(Token(TokenType.UNKNOWN, lex, start_line, start_col))
                else:
                    self.tokens.append(Token(TokenType.NUMBER, lex, start_line, start_col, literal=lex))
                continue

            # Operators (try two-char first)
            two = self._peek_n(2)
            if two in OPERATORS:
                self._advance_n(2)
                self.tokens.append(Token(TokenType.OPERATOR, two, start_line, start_col))
                continue

            # Single-char operator
            if ch in OPERATORS:
                self._advance()
                self.tokens.append(Token(TokenType.OPERATOR, ch, start_line, start_col))
                continue

            # Delimiters
            if ch in DELIMITERS:
                self._advance()
                self.tokens.append(Token(TokenType.DELIMITER, ch, start_line, start_col))
                continue

            # Unknown / illegal character
            self._add_error(f"Illegal character: {ch!r}", start_line, start_col)
            self._advance()

        # Append EOF token
        self.tokens.append(Token(TokenType.EOF, "<EOF>", self.line, self.column))
        return self.tokens, self.errors

    # ---- Low-level helpers / DFA-ish operations ----
    def _is_at_end(self) -> bool:
        return self.index >= self.length

    def _peek(self) -> str:
        return self.source[self.index] if not self._is_at_end() else "\0"

    def _peek_n(self, n: int) -> str:
        if self.index + n <= self.length:
            return self.source[self.index : self.index + n]
        return self.source[self.index : self.length]

    def _advance(self) -> str:
        ch = self._peek()
        self.index += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _advance_n(self, n: int) -> None:
        for _ in range(n):
            self._advance()

    def _consume_whitespace(self) -> None:
        while not self._is_at_end() and self._peek().isspace():
            self._advance()

    def _is_alpha(self, ch: str) -> bool:
        return ch.isalpha()

    def _consume_identifier(self) -> str:
        start = self.index
        # first char already known to be letter or underscore
        self._advance()
        while not self._is_at_end():
            c = self._peek()
            if c.isalnum() or c == "_":
                self._advance()
            else:
                break
        return self.source[start : self.index]

    def _consume_number(self) -> str:
        start = self.index
        has_dot = False
        # integer part
        while not self._is_at_end() and self._peek().isdigit():
            self._advance()

        # fractional part
        if not self._is_at_end() and self._peek() == ".":
            has_dot = True
            self._advance()
            if not self._is_at_end() and not self._peek().isdigit():
                # malformed like `12.` followed by non-digit => still accept `12.` but note later
                pass
            while not self._is_at_end() and self._peek().isdigit():
                self._advance()

        # If letters immediately follow (e.g., 123abc) consume them as part of malformed token
        while not self._is_at_end() and self._peek().isalpha():
            self._advance()

        return self.source[start : self.index]

    def _add_error(self, message: str, line: int, column: int) -> None:
        self.errors.append(LexError(message, line, column))


def simple_lex(source: str) -> Tuple[List[Token], List[LexError]]:
    """Convenience wrapper for quick usage in other modules or tests."""
    lexer = Lexer()
    return lexer.tokenize(source)


if __name__ == "__main__":
    # Quick manual smoke test when running the module directly.
    sample = """
    int a;
    a = 5 + 3 * (2 - 1);
    if (a > 5) { a = a - 1; }
    while (a < 10) { a = a + 1; }
    """
    toks, errs = simple_lex(sample)
    print("Tokens:")
    for t in toks:
        print(t)
    print("Errors:")
    for e in errs:
        print(e)
