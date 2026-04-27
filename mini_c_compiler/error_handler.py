"""Centralized error handling and phrase-level recovery utilities.

The ErrorHandler records parse errors and correction suggestions without
modifying the original token stream. Corrections are appended to the
parser's `corrected_tokens` list so the original `tokens` remain intact.
"""
from dataclasses import dataclass
from typing import List, Optional

from .tokens import Token, TokenType


@dataclass
class ParseError:
    message: str
    line: int
    column: int


@dataclass
class Correction:
    action: str  # 'insert' | 'delete' | 'replace' | 'skip'
    detail: str
    line: int
    column: int
    original: Optional[Token] = None
    replacement: Optional[Token] = None


class ErrorHandler:
    def __init__(self, parser) -> None:
        self.parser = parser
        self.corrections: List[Correction] = []

    def record_error(self, message: str, token: Optional[Token] = None) -> None:
        if token is None:
            token = self.parser.current()
        self.parser.errors.append(ParseError(message, token.line, token.column))

    def insert(self, lexeme: str, ttype: TokenType, line: int, column: int) -> Token:
        tok = Token(ttype, lexeme, line, column, corrected=True)
        self.parser.corrected_tokens.append(tok)
        self.corrections.append(Correction('insert', f"Inserted {lexeme!r}", line, column, replacement=tok))
        self.record_error(f"Inserted missing token {lexeme!r}", tok)
        return tok

    def delete_current(self) -> Optional[Token]:
        tok = self.parser.current()
        # advance without appending to corrected stream
        self.parser.consume_without_append()
        self.corrections.append(Correction('delete', f"Deleted {tok.lexeme!r}", tok.line, tok.column, original=tok))
        self.record_error(f"Deleted unexpected token {tok.lexeme!r}", tok)
        return tok

    def replace_current(self, new_lexeme: str, new_type: TokenType) -> Token:
        old = self.parser.current()
        # delete current token from consideration
        self.parser.consume_without_append()
        new_tok = Token(new_type, new_lexeme, old.line, old.column, corrected=True)
        self.parser.corrected_tokens.append(new_tok)
        self.corrections.append(Correction('replace', f"Replaced {old.lexeme!r} with {new_lexeme!r}", old.line, old.column, original=old, replacement=new_tok))
        self.record_error(f"Replaced {old.lexeme!r} with {new_lexeme!r}", old)
        return new_tok

    def panic(self) -> None:
        tok = self.parser.current()
        self.record_error("Panic: skipping tokens until statement boundary", tok)
        skipped = []
        while tok.lexeme not in (';', '}') and tok.type != TokenType.EOF:
            skipped.append(tok)
            self.parser.consume_without_append()
            tok = self.parser.current()
        for s in skipped:
            self.corrections.append(Correction('skip', f"Skipped {s.lexeme!r}", s.line, s.column, original=s))
            self.record_error(f"Skipped unexpected token {s.lexeme!r}", s)
        # consume the boundary token and append it to corrected stream so corrected
        # output remains syntactically consistent
        if tok.lexeme in (';', '}'):
            self.parser.advance()
            self.corrections.append(Correction('consume_boundary', f"Consumed boundary {tok.lexeme!r}", tok.line, tok.column, original=tok))
