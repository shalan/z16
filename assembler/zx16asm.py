#!/usr/bin/env python3
"""
ZX16 Assembler - A complete two-pass assembler for the ZX16 RISC architecture.

This assembler supports all ZX16 base instructions, pseudo-instructions, essential
directives, and multiple output formats including Verilog integration.

Author: ZX16 Development Team
License: MIT
"""

import argparse
import re
import sys
import os
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Union, Any
from pathlib import Path


class TokenType(Enum):
    """Token types for lexical analysis."""
    INSTRUCTION = auto()
    REGISTER = auto()
    IMMEDIATE = auto()
    LABEL = auto()
    DIRECTIVE = auto()
    STRING = auto()
    CHARACTER = auto()
    COMMENT = auto()
    NEWLINE = auto()
    COMMA = auto()
    COLON = auto()
    LPAREN = auto()
    RPAREN = auto()
    EOF = auto()


class OutputFormat(Enum):
    """Supported output formats."""
    BINARY = "bin"
    INTEL_HEX = "hex"
    VERILOG = "verilog"
    MEMORY = "mem"


@dataclass
class Token:
    """Represents a lexical token."""
    type: TokenType
    value: str
    line: int
    column: int


@dataclass
class AssemblyError:
    """Represents an assembly error."""
    message: str
    line: int
    column: int
    severity: str = "Error"  # Error, Warning, Info


@dataclass
class Symbol:
    """Represents a symbol in the symbol table."""
    name: str
    value: int
    defined: bool = False
    global_symbol: bool = False
    line: int = 0


@dataclass
class Instruction:
    """Represents a decoded instruction."""
    mnemonic: str
    operands: List[str] = field(default_factory=list)
    address: int = 0
    encoding: int = 0
    size: int = 2  # All ZX16 instructions are 2 bytes
    line: int = 0


class InstructionFormat(Enum):
    """ZX16 instruction formats."""
    R_TYPE = 0b000
    I_TYPE = 0b001
    B_TYPE = 0b010
    S_TYPE = 0b011
    L_TYPE = 0b100
    J_TYPE = 0b101
    U_TYPE = 0b110
    SYS_TYPE = 0b111


class ZX16Lexer:
    """Lexical analyzer for ZX16 assembly language."""
    
    def __init__(self, text: str, filename: str = "<input>"):
        self.text = text
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []
    
    def current_char(self) -> str:
        """Get the current character."""
        if self.pos >= len(self.text):
            return ''
        return self.text[self.pos]
    
    def peek_char(self, offset: int = 1) -> str:
        """Peek at character with offset."""
        peek_pos = self.pos + offset
        if peek_pos >= len(self.text):
            return ''
        return self.text[peek_pos]
    
    def advance(self) -> None:
        """Advance to the next character."""
        if self.pos < len(self.text) and self.text[self.pos] == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        self.pos += 1
    
    def skip_whitespace(self) -> None:
        """Skip whitespace except newlines."""
        while self.current_char() in ' \t\r':
            self.advance()
    
    def read_string(self) -> str:
        """Read a string literal."""
        result = ''
        self.advance()  # Skip opening quote
        
        while self.current_char() and self.current_char() != '"':
            if self.current_char() == '\\':
                self.advance()
                escape_char = self.current_char()
                escape_map = {
                    'n': '\n', 't': '\t', 'r': '\r', 
                    '\\': '\\', '"': '"'
                }
                result += escape_map.get(escape_char, escape_char)
            else:
                result += self.current_char()
            self.advance()
        
        if self.current_char() == '"':
            self.advance()  # Skip closing quote
        
        return result
    
    def read_number(self) -> int:
        """Read a numeric literal."""
        start_pos = self.pos
        
        # Handle different number bases
        if self.current_char() == '0' and self.peek_char():
            self.advance()
            if self.current_char().lower() == 'x':
                # Hexadecimal
                self.advance()
                while self.current_char().lower() in '0123456789abcdef':
                    self.advance()
                return int(self.text[start_pos:self.pos], 16)
            elif self.current_char().lower() == 'b':
                # Binary
                self.advance()
                while self.current_char() in '01':
                    self.advance()
                return int(self.text[start_pos:self.pos], 2)
            elif self.current_char().lower() == 'o':
                # Octal
                self.advance()
                while self.current_char() in '01234567':
                    self.advance()
                return int(self.text[start_pos:self.pos], 8)
            else:
                # Decimal starting with 0
                self.pos = start_pos
        
        # Decimal number
        while self.current_char().isdigit():
            self.advance()
        
        return int(self.text[start_pos:self.pos])
    
    def read_identifier(self) -> str:
        """Read an identifier."""
        start_pos = self.pos
        
        while (self.current_char().isalnum() or 
               self.current_char() in '_'):
            self.advance()
        
        return self.text[start_pos:self.pos]
    
    def is_register(self, identifier: str) -> bool:
        """Check if identifier is a register name."""
        register_names = {
            'x0', 'x1', 'x2', 'x3', 'x4', 'x5', 'x6', 'x7',
            't0', 'ra', 'sp', 's0', 's1', 't1', 'a0', 'a1'
        }
        return identifier.lower() in register_names
    
    def tokenize(self) -> List[Token]:
        """Tokenize the input text."""
        while self.pos < len(self.text):
            self.skip_whitespace()
            
            if not self.current_char():
                break
            
            line, column = self.line, self.column
            
            # Handle newlines
            if self.current_char() == '\n':
                self.tokens.append(Token(TokenType.NEWLINE, '\n', line, column))
                self.advance()
                continue
            
            # Handle comments
            if self.current_char() == '#':
                start_pos = self.pos
                while self.current_char() and self.current_char() != '\n':
                    self.advance()
                comment_text = self.text[start_pos:self.pos]
                self.tokens.append(Token(TokenType.COMMENT, comment_text, line, column))
                continue
            
            # Handle block comments
            if self.current_char() == '/' and self.peek_char() == '*':
                start_pos = self.pos
                self.advance()  # Skip '/'
                self.advance()  # Skip '*'
                while self.pos < len(self.text) - 1:
                    if self.current_char() == '*' and self.peek_char() == '/':
                        self.advance()  # Skip '*'
                        self.advance()  # Skip '/'
                        break
                    self.advance()
                comment_text = self.text[start_pos:self.pos]
                self.tokens.append(Token(TokenType.COMMENT, comment_text, line, column))
                continue
            
            # Handle single character tokens
            char_tokens = {
                ',': TokenType.COMMA,
                ':': TokenType.COLON,
                '(': TokenType.LPAREN,
                ')': TokenType.RPAREN
            }
            
            if self.current_char() in char_tokens:
                token_type = char_tokens[self.current_char()]
                self.tokens.append(Token(token_type, self.current_char(), line, column))
                self.advance()
                continue
            
            # Handle string literals
            if self.current_char() == '"':
                string_value = self.read_string()
                self.tokens.append(Token(TokenType.STRING, string_value, line, column))
                continue
            
            # Handle character literals
            if self.current_char() == "'":
                self.advance()  # Skip opening quote
                char_value = 0
                if self.current_char() == '\\':
                    self.advance()
                    escape_char = self.current_char()
                    escape_map = {
                        'n': ord('\n'), 't': ord('\t'), 'r': ord('\r'),
                        '\\': ord('\\'), "'": ord("'")
                    }
                    char_value = escape_map.get(escape_char, ord(escape_char))
                    self.advance()
                else:
                    char_value = ord(self.current_char())
                    self.advance()
                
                if self.current_char() == "'":
                    self.advance()  # Skip closing quote
                
                self.tokens.append(Token(TokenType.CHARACTER, str(char_value), line, column))
                continue
            
            # Handle negative numbers
            if self.current_char() == '-' and self.peek_char().isdigit():
                self.advance()  # Skip '-'
                number_value = -self.read_number()
                self.tokens.append(Token(TokenType.IMMEDIATE, str(number_value), line, column))
                continue
            
            # Handle numbers
            if self.current_char().isdigit():
                number_value = self.read_number()
                self.tokens.append(Token(TokenType.IMMEDIATE, str(number_value), line, column))
                continue
            
            # Handle directives
            if self.current_char() == '.':
                start_pos = self.pos
                self.advance()  # Skip '.'
                identifier = self.read_identifier()
                directive_name = self.text[start_pos:self.pos]
                self.tokens.append(Token(TokenType.DIRECTIVE, directive_name, line, column))
                continue
            
            # Handle identifiers, labels, instructions, and registers
            if self.current_char().isalpha() or self.current_char() == '_':
                identifier = self.read_identifier()
                
                # Check if it's followed by a colon (label)
                old_pos = self.pos
                self.skip_whitespace()
                if self.current_char() == ':':
                    self.advance()  # Consume the colon
                    self.tokens.append(Token(TokenType.LABEL, identifier, line, column))
                    continue
                else:
                    self.pos = old_pos  # Restore position
                
                # Check if it's a register
                if self.is_register(identifier):
                    self.tokens.append(Token(TokenType.REGISTER, identifier, line, column))
                else:
                    # Assume it's an instruction or symbol
                    self.tokens.append(Token(TokenType.INSTRUCTION, identifier, line, column))
                continue
            
            # Unknown character - skip it
            self.advance()
        
        self.tokens.append(Token(TokenType.EOF, '', self.line, self.column))
        return self.tokens


class ZX16Parser:
    """Parser for ZX16 assembly language."""
    
    def __init__(self, tokens: List[Token], filename: str = "<input>"):
        self.tokens = tokens
        self.filename = filename
        self.pos = 0
        self.current_token = self.tokens[0] if tokens else Token(TokenType.EOF, '', 1, 1)
        
        # Instruction encoding tables
        self.r_type_instructions = {
            'add': (0x0, 0x0), 'sub': (0x1, 0x0), 'slt': (0x2, 0x1), 'sltu': (0x3, 0x2),
            'sll': (0x4, 0x3), 'srl': (0x5, 0x3), 'sra': (0x6, 0x3), 'or': (0x7, 0x4),
            'and': (0x8, 0x5), 'xor': (0x9, 0x6), 'mv': (0xa, 0x7), 'jr': (0xb, 0x0),
            'jalr': (0xc, 0x0)
        }
        
        self.i_type_instructions = {
            'addi': 0x0, 'slti': 0x1, 'sltui': 0x2, 'ori': 0x4,
            'andi': 0x5, 'xori': 0x6, 'li': 0x7  # LI is a real I-Type instruction
        }
        
        self.shift_instructions = {
            'slli': 0x1, 'srli': 0x2, 'srai': 0x4
        }
        
        self.b_type_instructions = {
            'beq': 0x0, 'bne': 0x1, 'bz': 0x2, 'bnz': 0x3,
            'blt': 0x4, 'bge': 0x5, 'bltu': 0x6, 'bgeu': 0x7
        }
        
        self.s_type_instructions = {
            'sb': 0x0, 'sw': 0x1
        }
        
        self.l_type_instructions = {
            'lb': 0x0, 'lw': 0x1, 'lbu': 0x4
        }
        
        # Register name mapping
        self.register_map = {
            'x0': 0, 'x1': 1, 'x2': 2, 'x3': 3, 'x4': 4, 'x5': 5, 'x6': 6, 'x7': 7,
            't0': 0, 'ra': 1, 'sp': 2, 's0': 3, 's1': 4, 't1': 5, 'a0': 6, 'a1': 7
        }
        
        # Pseudo-instruction expansions (LI removed - it's handled specially)
        self.pseudo_instructions = {
            'li16', 'la', 'push', 'pop', 'call', 'ret',
            'inc', 'dec', 'neg', 'not', 'clr', 'nop'
        }
    
    def advance(self) -> None:
        """Move to the next token."""
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
            self.current_token = self.tokens[self.pos]
    
    def sign_extend(self, value: Union[int, str], bits: int) -> Union[int, str]:
        """Sign extend a value to specified bits."""
        if isinstance(value, str):
            return value  # Symbol, will be resolved later
        
        sign_bit = 1 << (bits - 1)
        mask = (1 << bits) - 1
        
        if value & sign_bit:
            return value | (~mask)
        return value & mask
    
    def expand_pseudo_instruction(self, mnemonic: str, operands: List[Union[int, str]], current_pc: int = 0, symbol_resolver=None) -> List[Tuple[str, List[Union[int, str]]]]:
        """Expand pseudo-instructions into base instructions."""
        expansions = []
        
        if mnemonic == 'li16':
            # LI16 rd, imm16 -> LUI rd, (imm16 >> 7); ORI rd, (imm16 & 0x7F)
            if len(operands) != 2:
                raise SyntaxError("LI16 requires 2 operands")
            rd, imm16 = operands
            
            if isinstance(imm16, str):
                # Symbol reference - try to resolve it
                if symbol_resolver:
                    imm16 = symbol_resolver(imm16)
                else:
                    # Defer expansion
                    return [(mnemonic, operands)]
            
            upper = (imm16 >> 7) & 0x1FF
            lower = imm16 & 0x7F
            
            expansions.append(('lui', [rd, upper]))
            expansions.append(('ori', [rd, lower]))
        
        elif mnemonic == 'la':
            # LA rd, label -> AUIPC rd, ((label-PC) >> 7); ADDI rd, ((label-PC) & 0x7F)
            if len(operands) != 2:
                raise SyntaxError("LA requires 2 operands")
            rd, label = operands
            
            if isinstance(label, str):
                if symbol_resolver:
                    label_addr = symbol_resolver(label)
                    offset = label_addr - current_pc
                    
                    # Calculate upper and lower parts for PC-relative addressing
                    if offset >= 0:
                        upper = (offset >> 7) & 0x1FF
                        lower = offset & 0x7F
                    else:
                        # Handle negative offsets
                        offset = offset & 0xFFFF  # 16-bit wrap
                        upper = (offset >> 7) & 0x1FF
                        lower = offset & 0x7F
                        if lower > 63:  # Sign extend lower part
                            lower = lower - 128
                    
                    expansions.append(('auipc', [rd, upper]))
                    expansions.append(('addi', [rd, lower]))
                else:
                    # Defer expansion to when symbols are available
                    return [(mnemonic, operands)]
            else:
                # Direct address
                offset = label - current_pc
                upper = (offset >> 7) & 0x1FF
                lower = offset & 0x7F
                
                expansions.append(('auipc', [rd, upper]))
                expansions.append(('addi', [rd, lower]))
        
        elif mnemonic == 'push':
            # PUSH rs -> ADDI sp, -2; SW rs, 0(sp)
            if len(operands) != 1:
                raise SyntaxError("PUSH requires 1 operand")
            rs = operands[0]
            sp = self.register_map['sp']
            
            expansions.append(('addi', [sp, -2]))
            expansions.append(('sw', [rs, 0, sp]))
        
        elif mnemonic == 'pop':
            # POP rd -> LW rd, 0(sp); ADDI sp, 2
            if len(operands) != 1:
                raise SyntaxError("POP requires 1 operand")
            rd = operands[0]
            sp = self.register_map['sp']
            
            expansions.append(('lw', [rd, 0, sp]))
            expansions.append(('addi', [sp, 2]))
        
        elif mnemonic == 'call':
            # CALL label -> JAL ra, label
            if len(operands) != 1:
                raise SyntaxError("CALL requires 1 operand")
            label = operands[0]
            ra = self.register_map['ra']
            
            expansions.append(('jal', [ra, label]))
        
        elif mnemonic == 'ret':
            # RET -> JR ra, 0 (JR needs 2 operands: rd and rs2, but rs2 is ignored)
            if len(operands) != 0:
                raise SyntaxError("RET requires 0 operands")
            ra = self.register_map['ra']
            
            expansions.append(('jr', [ra, 0]))  # JR ra with dummy rs2
        
        elif mnemonic == 'inc':
            # INC rd -> ADDI rd, 1
            if len(operands) != 1:
                raise SyntaxError("INC requires 1 operand")
            rd = operands[0]
            
            expansions.append(('addi', [rd, 1]))
        
        elif mnemonic == 'dec':
            # DEC rd -> ADDI rd, -1
            if len(operands) != 1:
                raise SyntaxError("DEC requires 1 operand")
            rd = operands[0]
            
            expansions.append(('addi', [rd, -1]))
        
        elif mnemonic == 'neg':
            # NEG rd -> XORI rd, -1; ADDI rd, 1
            if len(operands) != 1:
                raise SyntaxError("NEG requires 1 operand")
            rd = operands[0]
            
            expansions.append(('xori', [rd, -1]))
            expansions.append(('addi', [rd, 1]))
        
        elif mnemonic == 'not':
            # NOT rd -> XORI rd, -1
            if len(operands) != 1:
                raise SyntaxError("NOT requires 1 operand")
            rd = operands[0]
            
            expansions.append(('xori', [rd, -1]))
        
        elif mnemonic == 'clr':
            # CLR rd -> XOR rd, rd
            if len(operands) != 1:
                raise SyntaxError("CLR requires 1 operand")
            rd = operands[0]
            
            expansions.append(('xor', [rd, rd]))
        
        elif mnemonic == 'nop':
            # NOP -> ADD x0, x0
            if len(operands) != 0:
                raise SyntaxError("NOP requires 0 operands")
            
            expansions.append(('add', [0, 0]))
        
        return expansions


class ZX16Assembler:
    """Main assembler class for ZX16."""
    
    def __init__(self):
        self.symbols: Dict[str, Symbol] = {}
        self.instructions: List[Instruction] = []
        self.errors: List[AssemblyError] = []
        self.warnings: List[AssemblyError] = []
        self.current_address = 0x0020  # Default start address
        self.current_section = '.text'
        self.output_format = OutputFormat.BINARY
        self.verbose = False
        
        # Built-in symbols
        self.init_builtin_symbols()
        
        # Data sections
        self.sections = {
            '.text': bytearray(),
            '.data': bytearray(),
            '.bss': bytearray()
        }
        self.section_addresses = {
            '.text': 0x0020,
            '.data': 0x8000,
            '.bss': 0x9000
        }
    
    def init_builtin_symbols(self) -> None:
        """Initialize built-in symbols."""
        builtins = {
            '__ZX16__': 1,
            '__VERSION__': 0x0100,
            'RESET_VECTOR': 0x0000,
            'CODE_START': 0x0020,
            'MMIO_BASE': 0xF000,
            'MEM_SIZE': 0x10000,
            # Register aliases (removed STACK_TOP to avoid conflicts)
            'T0': 0, 'RA': 1, 'SP': 2, 'S0': 3,
            'S1': 4, 'T1': 5, 'A0': 6, 'A1': 7
        }
        
        for name, value in builtins.items():
            self.symbols[name] = Symbol(name, value, defined=True, global_symbol=True)
    
    def add_error(self, message: str, line: int, column: int = 0, severity: str = "Error") -> None:
        """Add an error to the error list."""
        error = AssemblyError(message, line, column, severity)
        if severity == "Error":
            self.errors.append(error)
        elif severity == "Warning":
            self.warnings.append(error)
    
    def resolve_symbol(self, name: str, line: int = 0) -> int:
        """Resolve a symbol to its value."""
        if name in self.symbols:
            symbol = self.symbols[name]
            if not symbol.defined:
                self.add_error(f"Undefined symbol '{name}'", line)
                return 0
            return symbol.value
        else:
            self.add_error(f"Unknown symbol '{name}'", line)
            return 0
    
    def define_symbol(self, name: str, value: int, line: int = 0, global_sym: bool = False) -> None:
        """Define a symbol."""
        if name in self.symbols:
            if self.symbols[name].defined:
                self.add_error(f"Symbol '{name}' already defined", line)
                return
        
        self.symbols[name] = Symbol(name, value, defined=True, global_symbol=global_sym, line=line)
    
    def assemble(self, source_code: str, filename: str = "<input>") -> bool:
        """Assemble source code."""
        try:
            # Tokenize
            lexer = ZX16Lexer(source_code, filename)
            tokens = lexer.tokenize()
            
            if self.verbose:
                print(f"Tokenized {len(tokens)} tokens")
            
            # Pass 1: Symbol collection
            self.pass1(tokens, filename)
            
            if self.errors:
                return False
            
            if self.verbose:
                print(f"Pass 1 complete. Found {len(self.symbols)} symbols")
            
            # Pass 2: Code generation
            self.pass2(tokens, filename)
            
            if self.verbose:
                print(f"Pass 2 complete. Generated {len(self.sections['.text'])} bytes of code")
            
            return len(self.errors) == 0
        
        except Exception as e:
            self.add_error(f"Internal assembler error: {str(e)}", 0)
            return False
    
    def pass1(self, tokens: List[Token], filename: str = "<input>") -> None:
        """First pass: collect symbols and calculate addresses."""
        parser = ZX16Parser(tokens, filename)
        self.current_address = self.section_addresses[self.current_section]
        
        while parser.current_token.type != TokenType.EOF:
            # Skip comments and newlines
            if parser.current_token.type in [TokenType.COMMENT, TokenType.NEWLINE]:
                parser.advance()
                continue
            
            line = parser.current_token.line
            
            # Handle labels
            if parser.current_token.type == TokenType.LABEL:
                label_name = parser.current_token.value
                self.define_symbol(label_name, self.current_address, line)
                parser.advance()
                continue
            
            # Handle directives
            if parser.current_token.type == TokenType.DIRECTIVE:
                directive = parser.current_token.value.lower()
                parser.advance()
                
                if directive == '.org':
                    if parser.current_token.type == TokenType.IMMEDIATE:
                        self.current_address = int(parser.current_token.value)
                        parser.advance()
                    else:
                        self.add_error("Expected address after .org", line)
                
                elif directive == '.text':
                    self.current_section = '.text'
                    self.current_address = self.section_addresses['.text']
                
                elif directive == '.data':
                    self.current_section = '.data'
                    self.current_address = self.section_addresses['.data']
                
                elif directive == '.bss':
                    self.current_section = '.bss'
                    self.current_address = self.section_addresses['.bss']
                
                elif directive in ['.equ', '.set']:
                    if parser.current_token.type == TokenType.INSTRUCTION:
                        symbol_name = parser.current_token.value
                        parser.advance()
                        if parser.current_token.type == TokenType.COMMA:
                            parser.advance()
                        if parser.current_token.type == TokenType.IMMEDIATE:
                            value = int(parser.current_token.value)
                            self.define_symbol(symbol_name, value, line)
                            parser.advance()
                        elif parser.current_token.type == TokenType.INSTRUCTION:
                            # Symbol reference
                            ref_symbol = parser.current_token.value
                            if ref_symbol in self.symbols:
                                value = self.symbols[ref_symbol].value
                                self.define_symbol(symbol_name, value, line)
                            else:
                                self.add_error(f"Undefined symbol '{ref_symbol}' in .equ", line)
                            parser.advance()
                        else:
                            self.add_error("Expected value after symbol name", line)
                    else:
                        self.add_error(f"Expected symbol name after {directive}", line)
                
                elif directive == '.global':
                    if parser.current_token.type == TokenType.INSTRUCTION:
                        symbol_name = parser.current_token.value
                        if symbol_name in self.symbols:
                            self.symbols[symbol_name].global_symbol = True
                        parser.advance()
                    else:
                        self.add_error("Expected symbol name after .global", line)
                
                elif directive in ['.byte', '.word', '.string', '.ascii', '.space']:
                    # Calculate space for data directives
                    if directive == '.byte':
                        while parser.current_token.type in [TokenType.IMMEDIATE, TokenType.CHARACTER]:
                            self.current_address += 1
                            parser.advance()
                            if parser.current_token.type == TokenType.COMMA:
                                parser.advance()
                            else:
                                break
                    
                    elif directive == '.word':
                        while parser.current_token.type == TokenType.IMMEDIATE:
                            self.current_address += 2
                            parser.advance()
                            if parser.current_token.type == TokenType.COMMA:
                                parser.advance()
                            else:
                                break
                    
                    elif directive in ['.string', '.ascii']:
                        if parser.current_token.type == TokenType.STRING:
                            string_len = len(parser.current_token.value)
                            if directive == '.string':
                                string_len += 1  # Null terminator
                            self.current_address += string_len
                            parser.advance()
                        else:
                            self.add_error(f"Expected string after {directive}", line)
                    
                    elif directive == '.space':
                        if parser.current_token.type == TokenType.IMMEDIATE:
                            space_size = int(parser.current_token.value)
                            self.current_address += space_size
                            parser.advance()
                        else:
                            self.add_error("Expected size after .space", line)
                
                # Skip to end of line for other directives
                while (parser.current_token.type not in [TokenType.NEWLINE, TokenType.EOF]):
                    parser.advance()
                continue
            
            # Handle instructions (including special LI handling)
            if parser.current_token.type == TokenType.INSTRUCTION:
                mnemonic = parser.current_token.value.lower()
                parser.advance()
                
                # Skip operands for pass 1 (just count instruction size)
                operand_count = 0
                has_immediate = False
                immediate_value = 0
                
                # Quick parse to check LI immediate size
                if mnemonic == 'li':
                    # Look for the immediate operand
                    temp_pos = parser.pos
                    while (parser.current_token.type not in [TokenType.NEWLINE, TokenType.EOF, TokenType.COMMENT]):
                        if parser.current_token.type == TokenType.COMMA:
                            parser.advance()
                        elif parser.current_token.type in [TokenType.IMMEDIATE, TokenType.CHARACTER]:
                            immediate_value = int(parser.current_token.value)
                            has_immediate = True
                            parser.advance()
                        else:
                            parser.advance()
                    parser.pos = temp_pos  # Restore position
                
                # Skip all operands
                while (parser.current_token.type not in [TokenType.NEWLINE, TokenType.EOF, TokenType.COMMENT]):
                    parser.advance()
                
                # Calculate instruction size
                if mnemonic == 'li' and has_immediate:
                    # LI: if immediate fits in 7 bits, it's I-Type (2 bytes)
                    # Otherwise, it's pseudo (expands to LI16 - 4 bytes)
                    if -64 <= immediate_value <= 63:
                        self.current_address += 2  # Real LI instruction
                    else:
                        self.current_address += 4  # Expands to LI16 (LUI + ORI)
                elif mnemonic in parser.pseudo_instructions:
                    if mnemonic in ['li16', 'neg']:
                        self.current_address += 4  # Expands to 2 instructions
                    else:
                        self.current_address += 2  # Most expand to 1 instruction
                else:
                    self.current_address += 2  # Regular instruction
                
                continue
            
            # Skip unknown tokens
            parser.advance()
    
    def pass2(self, tokens: List[Token], filename: str = "<input>") -> None:
        """Second pass: generate machine code."""
        parser = ZX16Parser(tokens, filename)
        self.current_address = self.section_addresses[self.current_section]
        current_section_data = self.sections[self.current_section]
        
        while parser.current_token.type != TokenType.EOF:
            # Skip comments and newlines
            if parser.current_token.type in [TokenType.COMMENT, TokenType.NEWLINE]:
                parser.advance()
                continue
            
            line = parser.current_token.line
            
            # Handle labels (already processed in pass 1)
            if parser.current_token.type == TokenType.LABEL:
                parser.advance()
                continue
            
            # Handle directives
            if parser.current_token.type == TokenType.DIRECTIVE:
                directive = parser.current_token.value.lower()
                parser.advance()
                
                if directive == '.org':
                    if parser.current_token.type == TokenType.IMMEDIATE:
                        self.current_address = int(parser.current_token.value)
                        parser.advance()
                
                elif directive == '.text':
                    self.current_section = '.text'
                    self.current_address = self.section_addresses['.text']
                    current_section_data = self.sections['.text']
                
                elif directive == '.data':
                    self.current_section = '.data'
                    self.current_address = self.section_addresses['.data']
                    current_section_data = self.sections['.data']
                
                elif directive == '.bss':
                    self.current_section = '.bss'
                    self.current_address = self.section_addresses['.bss']
                    current_section_data = self.sections['.bss']
                
                elif directive == '.byte':
                    while parser.current_token.type in [TokenType.IMMEDIATE, TokenType.CHARACTER]:
                        value = int(parser.current_token.value) & 0xFF
                        current_section_data.append(value)
                        self.current_address += 1
                        parser.advance()
                        if parser.current_token.type == TokenType.COMMA:
                            parser.advance()
                        else:
                            break
                
                elif directive == '.word':
                    while parser.current_token.type == TokenType.IMMEDIATE:
                        value = int(parser.current_token.value) & 0xFFFF
                        # Little-endian encoding
                        current_section_data.append(value & 0xFF)
                        current_section_data.append((value >> 8) & 0xFF)
                        self.current_address += 2
                        parser.advance()
                        if parser.current_token.type == TokenType.COMMA:
                            parser.advance()
                        else:
                            break
                
                elif directive in ['.string', '.ascii']:
                    if parser.current_token.type == TokenType.STRING:
                        string_data = parser.current_token.value.encode('utf-8')
                        current_section_data.extend(string_data)
                        self.current_address += len(string_data)
                        if directive == '.string':
                            current_section_data.append(0)  # Null terminator
                            self.current_address += 1
                        parser.advance()
                
                elif directive == '.space':
                    if parser.current_token.type == TokenType.IMMEDIATE:
                        space_size = int(parser.current_token.value)
                        current_section_data.extend([0] * space_size)
                        self.current_address += space_size
                        parser.advance()
                
                # Skip remaining tokens on this line
                while parser.current_token.type not in [TokenType.NEWLINE, TokenType.EOF]:
                    parser.advance()
                continue
            
            # Handle instructions (including special LI handling)
            if parser.current_token.type == TokenType.INSTRUCTION:
                mnemonic = parser.current_token.value.lower()
                parser.advance()
                
                # Parse operands
                operands = []
                while parser.current_token.type not in [TokenType.NEWLINE, TokenType.EOF, TokenType.COMMENT]:
                    
                    if parser.current_token.type == TokenType.COMMA:
                        parser.advance()
                        continue
                    
                    if parser.current_token.type == TokenType.REGISTER:
                        reg_name = parser.current_token.value.lower()
                        reg_num = parser.register_map.get(reg_name, 0)
                        operands.append(reg_num)
                        parser.advance()
                    
                    elif parser.current_token.type == TokenType.IMMEDIATE:
                        operands.append(int(parser.current_token.value))
                        parser.advance()
                    
                    elif parser.current_token.type == TokenType.CHARACTER:
                        operands.append(int(parser.current_token.value))
                        parser.advance()
                    
                    elif parser.current_token.type == TokenType.INSTRUCTION:
                        # Symbol reference
                        symbol_name = parser.current_token.value
                        symbol_value = self.resolve_symbol(symbol_name, line)
                        operands.append(symbol_value)
                        parser.advance()
                    
                    elif parser.current_token.type == TokenType.LPAREN:
                        # Memory operand: offset(register)
                        parser.advance()  # Skip '('
                        if parser.current_token.type == TokenType.REGISTER:
                            reg_name = parser.current_token.value.lower()
                            reg_num = parser.register_map.get(reg_name, 0)
                            operands.append(reg_num)
                            parser.advance()
                        if parser.current_token.type == TokenType.RPAREN:
                            parser.advance()  # Skip ')'
                    
                    else:
                        parser.advance()
                
                # Generate machine code
                try:
                    # Special handling for LI instruction
                    if mnemonic == 'li':
                        if len(operands) >= 2:
                            rd, imm = operands[0], operands[1]
                            
                            # Check if immediate fits in 7-bit signed range
                            if -64 <= imm <= 63:
                                # Use real LI instruction (I-Type)
                                encoding = self.encode_instruction(mnemonic, operands, parser)
                                if isinstance(encoding, int):
                                    current_section_data.append(encoding & 0xFF)
                                    current_section_data.append((encoding >> 8) & 0xFF)
                                    self.current_address += 2
                            else:
                                # Expand to LI16 (LUI + ORI)
                                def symbol_resolver(name):
                                    return self.resolve_symbol(name, line)
                                
                                expanded = parser.expand_pseudo_instruction('li16', [rd, imm], self.current_address, symbol_resolver)
                                for exp_mnemonic, exp_operands in expanded:
                                    encoding = self.encode_instruction(exp_mnemonic, exp_operands, parser)
                                    if isinstance(encoding, int):
                                        current_section_data.append(encoding & 0xFF)
                                        current_section_data.append((encoding >> 8) & 0xFF)
                                        self.current_address += 2
                        else:
                            raise SyntaxError("LI instruction requires 2 operands")
                    
                    elif mnemonic in parser.pseudo_instructions:
                        # Handle other pseudo-instruction expansion with symbol resolution
                        def symbol_resolver(name):
                            return self.resolve_symbol(name, line)
                        
                        expanded = parser.expand_pseudo_instruction(mnemonic, operands, self.current_address, symbol_resolver)
                        for exp_mnemonic, exp_operands in expanded:
                            encoding = self.encode_instruction(exp_mnemonic, exp_operands, parser)
                            if isinstance(encoding, int):
                                # Little-endian encoding
                                current_section_data.append(encoding & 0xFF)
                                current_section_data.append((encoding >> 8) & 0xFF)
                                self.current_address += 2
                    else:
                        # Regular instruction
                        encoding = self.encode_instruction(mnemonic, operands, parser)
                        if isinstance(encoding, int):
                            # Little-endian encoding
                            current_section_data.append(encoding & 0xFF)
                            current_section_data.append((encoding >> 8) & 0xFF)
                            self.current_address += 2
                
                except Exception as e:
                    self.add_error(f"Error encoding instruction '{mnemonic}': {str(e)}", line)
                    self.current_address += 2
                
                continue
            
            # Skip unknown tokens
            parser.advance()
    
    def encode_instruction(self, mnemonic: str, operands: List[Union[int, str]], parser: ZX16Parser) -> int:
        """Encode an instruction to machine code."""
        mnemonic = mnemonic.lower()
        
        # R-Type instructions
        if mnemonic in parser.r_type_instructions:
            funct4, func3 = parser.r_type_instructions[mnemonic]
            
            if mnemonic == 'jr':
                # JR only uses rd (first operand), rs2 is ignored
                if len(operands) < 1:
                    raise SyntaxError(f"JR instruction requires at least 1 operand")
                rd = operands[0]
                rs2 = 0  # rs2 is ignored for JR
            else:
                # Other R-type instructions need both operands
                if len(operands) < 2:
                    raise SyntaxError(f"R-Type instruction {mnemonic} requires 2 operands")
                rd = operands[0]
                rs2 = operands[1]
            
            encoding = (funct4 << 12) | (rs2 << 9) | (rd << 6) | (func3 << 3) | InstructionFormat.R_TYPE.value
            return encoding

        # I-Type instructions
        elif mnemonic in parser.i_type_instructions:
            if len(operands) < 2:
                raise SyntaxError(f"I-Type instruction {mnemonic} requires 2 operands")

            func3 = parser.i_type_instructions[mnemonic]
            rd = operands[0]
            imm = operands[1]

            if isinstance(imm, str):
               raise SyntaxError(f"Unresolved symbol in immediate: {imm}")

            if not isinstance(imm, int):
                raise SyntaxError(f"Immediate must be an integer or symbol, got {type(imm)}")

            if not -64 <= imm <= 63:
                raise SyntaxError(f"I-type immediate out of range: {imm}")

         # Encode: imm[6:0] << 9 | rd << 6 | func3 << 3 | opcode
            encoding = ((imm & 0x7F) << 9) | (rd << 6) | (func3 << 3) | InstructionFormat.I_TYPE.value
            return encoding

        # Shift instructions (special I-Type)
        elif mnemonic in parser.shift_instructions:
            if len(operands) < 2:
                raise SyntaxError(f"Shift instruction {mnemonic} requires 2 operands")
            
            rd = operands[0]
            shift_amt = operands[1]
            
            if isinstance(shift_amt, str) or shift_amt < 0 or shift_amt > 15:
                raise SyntaxError(f"Shift amount must be 0-15, got {shift_amt}")
            
            shift_type = parser.shift_instructions[mnemonic]
            imm7 = (shift_type << 4) | (shift_amt & 0xF)
            func3 = 0x3
            
            encoding = (imm7 << 9) | (rd << 6) | (func3 << 3) | InstructionFormat.I_TYPE.value
            return encoding
        
        # B-Type instructions
        elif mnemonic in parser.b_type_instructions:
            if mnemonic in ['bz', 'bnz']:
                if len(operands) < 2:
                    raise SyntaxError(f"Branch instruction {mnemonic} requires 2 operands")
                rs1, target = operands
                rs2 = 0  # Ignored for BZ/BNZ
            else:
                if len(operands) < 3:
                    raise SyntaxError(f"Branch instruction {mnemonic} requires 3 operands")
                rs1, rs2, target = operands
            
            func3 = parser.b_type_instructions[mnemonic]
            
            if isinstance(target, str):
                raise SyntaxError(f"Unresolved symbol in branch target: {target}")
            
            # Calculate relative offset
            offset = target - (self.current_address + 2)
            if offset < -32 or offset > 28 or offset % 2 != 0:
                raise SyntaxError(f"Branch offset out of range or not word-aligned: {offset}")
            
            imm_high = (offset >> 1) & 0xF
            encoding = (imm_high << 12) | (rs2 << 9) | (rs1 << 6) | (func3 << 3) | InstructionFormat.B_TYPE.value
            return encoding
        
        # S-Type instructions
        elif mnemonic in parser.s_type_instructions:
            if len(operands) < 3:
                raise SyntaxError(f"Store instruction {mnemonic} requires 3 operands")
            
            rs2, offset, rs1 = operands
            func3 = parser.s_type_instructions[mnemonic]
            
            if isinstance(offset, str):
                raise SyntaxError(f"Unresolved symbol in store offset: {offset}")
            
            if offset < -8 or offset > 7:
                raise SyntaxError(f"Store offset out of range: {offset}")
            
            encoding = ((offset & 0xF) << 12) | (rs2 << 9) | (rs1 << 6) | (func3 << 3) | InstructionFormat.S_TYPE.value
            return encoding
        
        # L-Type instructions
        elif mnemonic in parser.l_type_instructions:
            if len(operands) < 3:
                raise SyntaxError(f"Load instruction {mnemonic} requires 3 operands")
            
            rd, offset, rs2 = operands
            func3 = parser.l_type_instructions[mnemonic]
            
            if isinstance(offset, str):
                raise SyntaxError(f"Unresolved symbol in load offset: {offset}")
            
            if offset < -8 or offset > 7:
                raise SyntaxError(f"Load offset out of range: {offset}")
            
            encoding = ((offset & 0xF) << 12) | (rs2 << 9) | (rd << 6) | (func3 << 3) | InstructionFormat.L_TYPE.value
            return encoding
        
        # J-Type instructions
        elif mnemonic in ['j', 'jal']:
            if mnemonic == 'j':
                if len(operands) < 1:
                    raise SyntaxError("J instruction requires 1 operand")
                target = operands[0]
                rd = 0
                link = 0
            else:  # jal
                if len(operands) < 2:
                    raise SyntaxError("JAL instruction requires 2 operands")
                rd, target = operands
                link = 1
            
            if isinstance(target, str):
                raise SyntaxError(f"Unresolved symbol in jump target: {target}")
            
            offset = target - (self.current_address + 2)
            if offset < -1024 or offset > 1020 or offset % 2 != 0:
                raise SyntaxError(f"Jump offset out of range or not word-aligned: {offset}")
            
            imm_high = (offset >> 4) & 0x3F
            imm_low = (offset >> 1) & 0x7
            
            encoding = (link << 15) | (imm_high << 9) | (rd << 6) | (imm_low << 3) | InstructionFormat.J_TYPE.value
            return encoding
        
        # U-Type instructions
        elif mnemonic in ['lui', 'auipc']:
            if len(operands) < 2:
                raise SyntaxError(f"U-Type instruction {mnemonic} requires 2 operands")
            
            rd, immediate = operands
            flag = 1 if mnemonic == 'auipc' else 0
            
            if isinstance(immediate, str):
                raise SyntaxError(f"Unresolved symbol in U-Type immediate: {immediate}")
            
            # U-Type immediate is 9 bits
            if immediate < 0 or immediate > 0x1FF:
                raise SyntaxError(f"U-Type immediate out of range: {immediate}")
            
            imm_high = (immediate >> 3) & 0x3F
            imm_low = immediate & 0x7
            
            encoding = (flag << 15) | (imm_high << 9) | (rd << 6) | (imm_low << 3) | InstructionFormat.U_TYPE.value
            return encoding
        
        # SYS-Type instructions
        elif mnemonic == 'ecall':
            if len(operands) < 1:
                raise SyntaxError("ECALL instruction requires 1 operand")
            
            svc = operands[0]
            if isinstance(svc, str):
                raise SyntaxError(f"Unresolved symbol in system call: {svc}")
            
            # Handle both decimal and hex service numbers
            if svc < 0 or svc > 0x3FF:
                raise SyntaxError(f"System call number out of range (0-1023): {svc}")
            
            encoding = (svc << 6) | InstructionFormat.SYS_TYPE.value
            return encoding
        
        else:
            raise SyntaxError(f"Unknown instruction: {mnemonic}")
    
    def get_binary_output(self) -> bytes:
        """Get binary output."""
        # Combine all sections
        output = bytearray(65536)  # 64KB memory space
        
        # Write text section
        text_start = self.section_addresses['.text']
        text_data = self.sections['.text']
        output[text_start:text_start + len(text_data)] = text_data
        
        # Write data section
        data_start = self.section_addresses['.data']
        data_data = self.sections['.data']
        output[data_start:data_start + len(data_data)] = data_data
        
        return bytes(output)
    
    def get_intel_hex_output(self) -> str:
        """Get Intel HEX format output."""
        lines = []
        
        def write_hex_line(address: int, data: bytes, record_type: int = 0) -> str:
            line = f":{len(data):02X}{address:04X}{record_type:02X}"
            line += data.hex().upper()
            
            # Calculate checksum
            checksum = len(data) + (address >> 8) + (address & 0xFF) + record_type
            for byte in data:
                checksum += byte
            checksum = (-checksum) & 0xFF
            
            line += f"{checksum:02X}"
            return line
        
        # Write text section
        text_data = self.sections['.text']
        if text_data:
            text_start = self.section_addresses['.text']
            for i in range(0, len(text_data), 16):
                chunk = text_data[i:i + 16]
                lines.append(write_hex_line(text_start + i, chunk))
        
        # Write data section
        data_data = self.sections['.data']
        if data_data:
            data_start = self.section_addresses['.data']
            for i in range(0, len(data_data), 16):
                chunk = data_data[i:i + 16]
                lines.append(write_hex_line(data_start + i, chunk))
        
        # End of file record
        lines.append(":00000001FF")
        
        return '\n'.join(lines)
    
    def get_verilog_output(self, module_name: str = "program_memory") -> str:
        """Get Verilog module output."""
        lines = [
            "// ZX16 Program Memory Initialization",
            "// Generated by ZX16 Assembler",
            "",
            f"module {module_name}(",
            "    input [15:0] addr,",
            "    output reg [15:0] data",
            ");",
            "",
            "always @(*) begin",
            "    case (addr)"
        ]
        
        # Add text section data
        text_data = self.sections['.text']
        text_start = self.section_addresses['.text']
        for i in range(0, len(text_data), 2):
            if i + 1 < len(text_data):
                word = text_data[i] | (text_data[i + 1] << 8)
                addr = text_start + i
                lines.append(f"        16'h{addr:04X}: data = 16'h{word:04X};")
        
        # Add data section data
        data_data = self.sections['.data']
        data_start = self.section_addresses['.data']
        for i in range(0, len(data_data), 2):
            if i + 1 < len(data_data):
                word = data_data[i] | (data_data[i + 1] << 8)
                addr = data_start + i
                lines.append(f"        16'h{addr:04X}: data = 16'h{word:04X};")
        
        lines.extend([
            "        default: data = 16'h0000;",
            "    endcase",
            "end",
            "",
            "endmodule"
        ])
        
        return '\n'.join(lines)
    
    def get_memory_file_output(self, sparse: bool = False) -> str:
        """Get memory file output for $readmemh."""
        if sparse:
            lines = ["# ZX16 Sparse Memory File"]
            
            # Text section
            text_data = self.sections['.text']
            text_start = self.section_addresses['.text']
            for i in range(0, len(text_data), 2):
                if i + 1 < len(text_data):
                    word = text_data[i] | (text_data[i + 1] << 8)
                    addr = text_start + i
                    lines.append(f"@{addr:04X} {word:04X}")
            
            # Data section
            data_data = self.sections['.data']
            data_start = self.section_addresses['.data']
            for i in range(0, len(data_data), 2):
                if i + 1 < len(data_data):
                    word = data_data[i] | (data_data[i + 1] << 8)
                    addr = data_start + i
                    lines.append(f"@{addr:04X} {word:04X}")
        
        else:
            lines = ["# ZX16 Memory File"]
            memory = [0] * 32768  # 64KB / 2 bytes per word
            
            # Fill text section
            text_data = self.sections['.text']
            text_start = self.section_addresses['.text'] // 2
            for i in range(0, len(text_data), 2):
                if i + 1 < len(text_data):
                    word = text_data[i] | (text_data[i + 1] << 8)
                    memory[text_start + i // 2] = word
            
            # Fill data section
            data_data = self.sections['.data']
            data_start = self.section_addresses['.data'] // 2
            for i in range(0, len(data_data), 2):
                if i + 1 < len(data_data):
                    word = data_data[i] | (data_data[i + 1] << 8)
                    memory[data_start + i // 2] = word
            
            # Output all memory words
            for word in memory:
                lines.append(f"{word:04X}")
        
        return '\n'.join(lines)
    
    def get_listing_output(self, source_lines: List[str]) -> str:
        """Generate assembly listing."""
        lines = [
            "ZX16 Assembler Listing",
            "=" * 50,
            "",
        ]
        
        # Add source with line numbers
        for i, source_line in enumerate(source_lines, 1):
            line_output = f"{i:4d}      {source_line}"
            lines.append(line_output)
        
        lines.extend([
            "",
            "Symbol Table:",
            "-" * 30
        ])
        
        # Add symbol table
        for name, symbol in sorted(self.symbols.items()):
            if symbol.defined and not name.startswith('__'):
                scope = "global" if symbol.global_symbol else "local"
                lines.append(f"{name:<20} = 0x{symbol.value:04X}  ({scope})")
        
        lines.extend([
            "",
            "Statistics:",
            f"  Code size:    {len(self.sections['.text'])} bytes",
            f"  Data size:    {len(self.sections['.data'])} bytes",
            f"  Total size:   {len(self.sections['.text']) + len(self.sections['.data'])} bytes",
            f"  Symbols:      {len([s for s in self.symbols.values() if s.defined])}",
            f"  Lines:        {len(source_lines)}"
        ])
        
        return '\n'.join(lines)
    
    def print_errors(self) -> None:
        """Print all errors and warnings."""
        for error in self.errors:
            print(f"Error at line {error.line}: {error.message}", file=sys.stderr)
        
        for warning in self.warnings:
            print(f"Warning at line {warning.line}: {warning.message}", file=sys.stderr)
        
        if self.errors:
            print(f"\nAssembly failed with {len(self.errors)} errors, {len(self.warnings)} warnings.",
                  file=sys.stderr)
        elif self.warnings:
            print(f"\nAssembly completed with {len(self.warnings)} warnings.")
        else:
            print("Assembly completed successfully.")


def main():
    """Main entry point for the assembler."""
    parser = argparse.ArgumentParser(description="ZX16 Assembler")
    parser.add_argument("input", help="Input assembly file")
    parser.add_argument("-o", "--output", help="Output file")
    parser.add_argument("-f", "--format", choices=["bin", "hex", "verilog", "mem"],
                       default="bin", help="Output format")
    parser.add_argument("-l", "--listing", help="Generate listing file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--verilog-module", default="program_memory",
                       help="Verilog module name")
    parser.add_argument("--mem-sparse", action="store_true",
                       help="Generate sparse memory file")
    
    args = parser.parse_args()
    
    # Read input file
    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            source_code = f.read()
            source_lines = source_code.splitlines()
    except FileNotFoundError:
        print(f"Error: Input file '{args.input}' not found", file=sys.stderr)
        return 1
    except IOError as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        return 1
    
    # Create assembler
    assembler = ZX16Assembler()
    assembler.verbose = args.verbose
    
    # Assemble
    success = assembler.assemble(source_code, args.input)
    
    # Print errors/warnings
    assembler.print_errors()
    
    if not success:
        return 1
    
    # Generate output
    if args.output:
        output_file = args.output
    else:
        # Generate default output filename
        input_path = Path(args.input)
        if args.format == "bin":
            output_file = input_path.with_suffix('.bin')
        elif args.format == "hex":
            output_file = input_path.with_suffix('.hex')
        elif args.format == "verilog":
            output_file = input_path.with_suffix('.v')
        elif args.format == "mem":
            output_file = input_path.with_suffix('.mem')
    
    try:
        if args.format == "bin":
            output_data = assembler.get_binary_output()
            with open(output_file, 'wb') as f:
                f.write(output_data)
        
        elif args.format == "hex":
            output_data = assembler.get_intel_hex_output()
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(output_data)
        
        elif args.format == "verilog":
            output_data = assembler.get_verilog_output(args.verilog_module)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(output_data)
        
        elif args.format == "mem":
            output_data = assembler.get_memory_file_output(args.mem_sparse)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(output_data)
        
        if args.verbose:
            print(f"Output written to {output_file}")
        
        # Generate listing file if requested
        if args.listing:
            listing_content = assembler.get_listing_output(source_lines)
            with open(args.listing, 'w', encoding='utf-8') as f:
                f.write(listing_content)
            if args.verbose:
                print(f"Listing written to {args.listing}")
        
    except IOError as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
