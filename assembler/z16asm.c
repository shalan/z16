/*
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * 
 * A 2‑pass assembler for the Z16 16‑bit ISA.
 *
 * Author: Mohamed Shalan
 * Special thanks to ChatGPT for its assistance in the development ;).
 *
 * =============================================================================
 *
 * Functional Requirements for the Z16 16‑Bit Assembler
 *
 * [See specification details in the attached Z16 ISA Specification PDF]
 *
 */

 #include <stdio.h>
 #include <stdlib.h>
 #include <string.h>
 #include <ctype.h>
 #include <stdint.h>
 
 #define MAX_LINE_LENGTH 256
 #define MAX_LABEL_LENGTH 64
 #define MAX_LINES 2048
 // Total memory is 64KB
 #define MEM_SIZE 65536
 
 // -----------------------
 // Utility Functions
 // -----------------------
 
 // Convert a string in-place to lower-case.
 void toLowerStr(char *str) {
     for (; *str; str++)
         *str = tolower((unsigned char)*str);
 }
 
 // Compare two strings case-insensitively.
 int cmpIgnoreCase(const char* s1, const char* s2) {
     while(*s1 && *s2) {
          char c1 = tolower((unsigned char)*s1);
          char c2 = tolower((unsigned char)*s2);
          if(c1 != c2)
              return c1 - c2;
          s1++;
          s2++;
     }
     return tolower((unsigned char)*s1) - tolower((unsigned char)*s2);
 }
 
 // Trim whitespace from both ends of a string.
 void trim(char *s) {
     char *p = s;
     while(isspace((unsigned char)*p)) p++;
     if(p != s) memmove(s, p, strlen(p) + 1);
     char *end = s + strlen(s) - 1;
     while(end >= s && isspace((unsigned char)*end)) {
         *end = '\0';
         end--;
     }
 }
 
 // Count comma-separated values in a directive operand string.
 int countValues(const char *operands) {
     int count = 0;
     char temp[MAX_LINE_LENGTH];
     strncpy(temp, operands, MAX_LINE_LENGTH);
     char *token = strtok(temp, ",");
     while(token != NULL) {
         count++;
         token = strtok(NULL, ",");
     }
     return count;
 }
 
 // -----------------------
 // Symbol Table Structures and Functions
 // -----------------------
 
 typedef enum { SECTION_NONE, SECTION_TEXT, SECTION_DATA } Section;
 
 typedef struct Symbol {
     char name[MAX_LABEL_LENGTH]; // stored in lower-case
     int address;                 // address where the label is defined
     Section section;             // TEXT or DATA
     struct Symbol *next;         // chaining
 } Symbol;
 
 Symbol *symbolTable = NULL;
 
 // Add a symbol to the symbol table (the name is stored in lower-case).
 int addSymbol(const char *name, int address, Section sec) {
     Symbol *cur = symbolTable;
     while(cur) {
         if(cmpIgnoreCase(cur->name, name) == 0) {
             fprintf(stderr, "Error: Duplicate label '%s'\n", name);
             return -1;
         }
         cur = cur->next;
     }
     Symbol *newSym = (Symbol *)malloc(sizeof(Symbol));
     if(!newSym) { perror("malloc"); exit(1); }
     strncpy(newSym->name, name, MAX_LABEL_LENGTH);
     newSym->name[MAX_LABEL_LENGTH-1] = '\0';
     toLowerStr(newSym->name);
     newSym->address = address;
     newSym->section = sec;
     newSym->next = symbolTable;
     symbolTable = newSym;
     return 0;
 }
 
 // Lookup a symbol by name (case-insensitive).
 Symbol* findSymbol(const char *name) {
     Symbol *cur = symbolTable;
     while(cur) {
         if(cmpIgnoreCase(cur->name, name) == 0)
             return cur;
         cur = cur->next;
     }
     return NULL;
 }
 
 // -----------------------
 // Instruction Encoding Structures and Table
 // -----------------------

 typedef enum { INST_R, INST_I, INST_B, INST_L, INST_J, INST_U, INST_S } InstType;

 typedef struct {
     char *mnemonic;    // stored in lower-case
     InstType type;     // instruction type
     int opcode;        // opcode field
     int funct3;        // funct3 field when applicable
     int funct4;        // funct4 field for R-type instructions
 } InstructionDef;

 InstructionDef instructionSet[] = {
     {"add",   INST_R, 0, 0, 0x0},
     {"sub",   INST_R, 0, 0, 0x1},
     {"slt",   INST_R, 0, 1, 0x0},
     {"sltu",  INST_R, 0, 2, 0x0},
     {"sll",   INST_R, 0, 3, 0x2},
     {"srl",   INST_R, 0, 3, 0x4},
     {"sra",   INST_R, 0, 3, 0x8},
     {"or",    INST_R, 0, 4, 0x1},
     {"and",   INST_R, 0, 5, 0x0},
     {"xor",   INST_R, 0, 6, 0x4},
     {"mv",    INST_R, 0, 7, 0x0},
     {"jr",    INST_R, 0, 0, 0x4},
     {"jalr",  INST_R, 0, 0, 0x8},
     {"addi",  INST_I, 1, 0, 0},
     {"slti",  INST_I, 1, 1, 0},
     {"sltui", INST_I, 1, 2, 0},
     {"slli",  INST_I, 1, 3, 0},
     {"srli",  INST_I, 1, 3, 0},
     {"srai",  INST_I, 1, 3, 0},
     {"ori",   INST_I, 1, 4, 0},
     {"andi",  INST_I, 1, 5, 0},
     {"xori",   INST_I, 1, 6, 0},
     {"li",    INST_I, 1, 7, 0},
     {"beq",   INST_B, 2, 0, 0},
     {"bne",   INST_B, 2, 1, 0},
     {"bz",    INST_B, 2, 2, 0},
     {"bnz",   INST_B, 2, 3, 0},
     {"blt",   INST_B, 2, 4, 0},
     {"bge",   INST_B, 2, 5, 0},
     {"bltu",  INST_B, 2, 6, 0},
     {"bgeu",  INST_B, 2, 7, 0},
     {"lb",    INST_L, 4, 0, 0},
     {"lw",    INST_L, 4, 1, 0},
     {"lbu",   INST_L, 4, 4, 0},
     {"sb",    INST_L, 3, 0, 0},
     {"sw",    INST_L, 3, 1, 0},
     {"j",     INST_J, 5, 0, 0},
     {"jal",   INST_J, 5, 0, 0},
     {"lui",   INST_U, 6, 0, 0},
     {"auipc", INST_U, 6, 0, 0},
     {"ecall", INST_S, 7, 0, 0},
     {NULL, 0, 0, 0, 0} // end marker
 };

 // Lookup instruction definition (case-insensitive).
 InstructionDef* lookupInstruction(const char *mnemonic) {
     for (int i = 0; instructionSet[i].mnemonic != NULL; i++) {
         if (cmpIgnoreCase(mnemonic, instructionSet[i].mnemonic) == 0)
             return &instructionSet[i];
     }
     return NULL;
 }

 // -----------------------
 // Register and Immediate Parsing
 // -----------------------

 // Convert a register name (e.g. "X3" or "s0") to its register number.
 int parseRegister(const char *token) {
     if(token[0]=='x' || token[0]=='X') {
         int reg = atoi(token+1);
         if(reg < 0 || reg > 7) {
             fprintf(stderr, "Error: Invalid register number '%s'\n", token);
             exit(1);
         }
         return reg;
     }
     if(cmpIgnoreCase(token, "t0") == 0) return 0;
     if(cmpIgnoreCase(token, "ra") == 0) return 1;
     if(cmpIgnoreCase(token, "sp") == 0) return 2;
     if(cmpIgnoreCase(token, "s0") == 0) return 3;
     if(cmpIgnoreCase(token, "s1") == 0) return 4;
     if(cmpIgnoreCase(token, "t1") == 0) return 5;
     if(cmpIgnoreCase(token, "a0") == 0) return 6;
     if(cmpIgnoreCase(token, "a1") == 0) return 7;
     fprintf(stderr, "Error: Unknown register '%s'\n", token);
     exit(1);
     return -1;
 }

 // Parse an immediate value. Supports decimal, octal, hex, binary, %hi(...) and %lo(...).
 int parseImmediate(const char *token) {
     if(strncmp(token, "%hi(", 4)==0) {
         const char *p = token + 4;
         char numberStr[64];
         int i = 0;
         while(*p && *p != ')') {
             numberStr[i++] = *p++;
         }
         numberStr[i] = '\0';
         int value = (int)strtol(numberStr, NULL, 0);
         return value >> 7;
     }
     if(strncmp(token, "%lo(", 4)==0) {
         const char *p = token + 4;
         char numberStr[64];
         int i = 0;
         while(*p && *p != ')') {
             numberStr[i++] = *p++;
         }
         numberStr[i] = '\0';
         int value = (int)strtol(numberStr, NULL, 0);
         return value & 0x7F;
     }
     // Support binary constants with "0b" or "0B" prefix.
     if(token[0]=='0' && (token[1]=='b' || token[1]=='B'))
         return (int)strtol(token+2, NULL, 2);
     return (int)strtol(token, NULL, 0);
 }

 // -----------------------
 // Source Line Structures and Parsing
 // -----------------------

 // Each code element’s size: for instructions and .word, 2 bytes; for .byte and .asciiz, 1 byte.
 typedef struct {
     int lineNo;                      // source line number
     char original[MAX_LINE_LENGTH];  // original source text
     int address;                     // computed address
     Section section;                 // TEXT or DATA
     char *label;                     // label (if any)
     char *mnemonic;                  // directive or instruction mnemonic (in lower-case)
     char *operands;                  // operand string
     uint16_t *code;                  // array of code elements (each stored in 16 bits)
     int codeCount;                   // number of code elements
     int elementSize;                 // size in bytes for each code element (1 or 2)
 } Line;

 Line *lines[MAX_LINES];
 int lineCount = 0;

 // -----------------------
 // Global Location Counters and Section Tracking
 // -----------------------

 int loc_text = 0;  // text section location counter (in bytes)
 int loc_data = 0;  // data section location counter (in bytes)
 Section currentSection = SECTION_NONE;

 // -----------------------
 // Source Line Parsing Functions
 // -----------------------

 Line* newLine(int lineNo, const char *src) {
     Line *l = (Line *)malloc(sizeof(Line));
     if(!l) { perror("malloc"); exit(1); }
     l->lineNo = lineNo;
     strncpy(l->original, src, MAX_LINE_LENGTH);
     l->address = 0;
     l->section = currentSection;
     l->label = NULL;
     l->mnemonic = NULL;
     l->operands = NULL;
     l->code = NULL;
     l->codeCount = 0;
     l->elementSize = 0;
     return l;
 }

 void freeLine(Line *l) {
     if(l) {
         if(l->mnemonic) free(l->mnemonic);
         if(l->operands) free(l->operands);
         if(l->code) free(l->code);
         free(l);
     }
 }

 // Parse a source line into label, mnemonic, and operands.
 // Comments (starting with '#' or ';') are removed and the mnemonic is converted to lower-case.
 void parseSourceLine(Line *line) {
     char buffer[MAX_LINE_LENGTH];
     strncpy(buffer, line->original, MAX_LINE_LENGTH);
     char *com = strpbrk(buffer, "#;");
     if(com) *com = '\0';
     trim(buffer);
     if(strlen(buffer) == 0)
         return;
     char *colon = strchr(buffer, ':');
     if(colon) {
         *colon = '\0';
         trim(buffer);
         line->label = strdup(buffer);
         // addSymbol converts the label to lower-case.
         if(addSymbol(line->label, (currentSection==SECTION_TEXT)? loc_text : loc_data, currentSection) != 0) {
             fprintf(stderr, "Error on line %d: Duplicate label %s\n", line->lineNo, line->label);
             exit(1);
         }
         char *rest = colon + 1;
         trim(rest);
         if(strlen(rest)==0)
             return;
         strcpy(buffer, rest);
     }
     char *token = strtok(buffer, " \t");
     if(token) {
         line->mnemonic = strdup(token);
         toLowerStr(line->mnemonic);
         char *ops = strtok(NULL, "\n");
         if(ops) {
             while(isspace((unsigned char)*ops)) ops++;
             line->operands = strdup(ops);
         }
     }
 }

 // -----------------------
 // Pass 1: Build Symbol Table and Assign Addresses
 // -----------------------

 void pass1(FILE *fp) {
     char srcLine[MAX_LINE_LENGTH];
     int currentLineNo = 0;
     while(fgets(srcLine, sizeof(srcLine), fp)) {
         currentLineNo++;
         Line *line = newLine(currentLineNo, srcLine);
         parseSourceLine(line);
         line->section = currentSection;
         if(currentSection == SECTION_TEXT)
             line->address = loc_text;
         else if(currentSection == SECTION_DATA)
             line->address = loc_data;
         else
             line->address = 0;

         if(line->mnemonic && line->mnemonic[0]=='.') {
             if(cmpIgnoreCase(line->mnemonic, ".text") == 0) {
                 currentSection = SECTION_TEXT;
             } else if(cmpIgnoreCase(line->mnemonic, ".data") == 0) {
                 currentSection = SECTION_DATA;
             } else if(cmpIgnoreCase(line->mnemonic, ".org") == 0) {
                 if(line->operands==NULL) {
                     fprintf(stderr, "Error on line %d: .org missing operand\n", line->lineNo);
                     exit(1);
                 }
                 int newOrg = (int)strtol(line->operands, NULL, 0);
                 if(currentSection==SECTION_TEXT) {
                     loc_text = newOrg;
                     line->address = loc_text;
                 } else if(currentSection==SECTION_DATA) {
                     loc_data = newOrg;
                     line->address = loc_data;
                 }
             } else if(cmpIgnoreCase(line->mnemonic, ".asciiz") == 0) {
                 if(line->operands==NULL) {
                     fprintf(stderr, "Error on line %d: .asciiz missing string operand\n", line->lineNo);
                     exit(1);
                 }
                 char *s = line->operands;
                 if(s[0]=='"' && s[strlen(s)-1]=='"') {
                     s[strlen(s)-1] = '\0';
                     s++;
                 }
                 int len = (int)strlen(s) + 1;
                 line->elementSize = 1; // each character is a byte
                 loc_data += len;
             } else if(cmpIgnoreCase(line->mnemonic, ".byte") == 0) {
                 if(line->operands==NULL) {
                     fprintf(stderr, "Error on line %d: .byte missing operand\n", line->lineNo);
                     exit(1);
                 }
                 int count = countValues(line->operands);
                 line->elementSize = 1;
                 loc_data += count;
             } else if(cmpIgnoreCase(line->mnemonic, ".word") == 0) {
                 if(line->operands==NULL) {
                     fprintf(stderr, "Error on line %d: .word missing operand\n", line->lineNo);
                     exit(1);
                 }
                 int count = countValues(line->operands);
                 line->elementSize = 2;
                 loc_data += count * 2;
             } else if(cmpIgnoreCase(line->mnemonic, ".space") == 0) {
                 if(line->operands==NULL) {
                     fprintf(stderr, "Error on line %d: .space missing operand\n", line->lineNo);
                     exit(1);
                 }
                 int spaceSize = (int)strtol(line->operands, NULL, 0);
                 line->elementSize = 1;
                 loc_data += spaceSize;
             }
         } else if(line->mnemonic) {
             // For instructions, each produces 2 bytes.
             if(currentSection==SECTION_TEXT) {
                 line->elementSize = 2;
                 loc_text += 2;
             }
         }
         lines[lineCount++] = line;
     }
     rewind(fp);
 }

 // -----------------------
 // Pass 2: Encode Instructions and Process Data Directives
 // -----------------------

 void pass2() {
     loc_text = 0;
     loc_data = 0;
     for (int i = 0; i < lineCount; i++) {
         Line *line = lines[i];
         if(line->mnemonic && line->mnemonic[0]=='.') {
             if(cmpIgnoreCase(line->mnemonic, ".org") == 0) {
                 if(currentSection == SECTION_TEXT && line->section==SECTION_TEXT)
                     loc_text = line->address;
                 else if(currentSection == SECTION_DATA && line->section==SECTION_DATA)
                     loc_data = line->address;
             } else if(cmpIgnoreCase(line->mnemonic, ".asciiz") == 0) {
                 char *s = line->operands;
                 if(s[0]=='"' && s[strlen(s)-1]=='"') {
                     s[strlen(s)-1] = '\0';
                     s++;
                 }
                 int len = (int)strlen(s) + 1;
                 // For .asciiz, allocate one 16-bit word per two characters.
                 line->codeCount = (len + 1) / 2;
                 line->code = (uint16_t *)malloc(line->codeCount * sizeof(uint16_t));
                 // Pack characters into words (little-endian).
                 for (int j = 0; j < line->codeCount; j++) {
                     uint16_t word = 0;
                     int index = j * 2;
                     if(index < len)
                         word |= ((unsigned char)s[index]);
                     if(index+1 < len)
                         word |= (((unsigned char)s[index+1]) << 8);
                     line->code[j] = word;
                 }
                 loc_data += len;
             } else if(cmpIgnoreCase(line->mnemonic, ".byte") == 0) {
                 int count = countValues(line->operands);
                 line->codeCount = count;
                 line->code = (uint16_t *)malloc(count * sizeof(uint16_t));
                 char *temp = strdup(line->operands);
                 char *token = strtok(temp, ",");
                 int idx = 0;
                 while(token) {
                     trim(token);
                     int val = parseImmediate(token);
                     line->code[idx++] = (uint16_t)(val & 0xFF);
                     token = strtok(NULL, ",");
                 }
                 free(temp);
                 loc_data += count;
             } else if(cmpIgnoreCase(line->mnemonic, ".word") == 0) {
                 int count = countValues(line->operands);
                 line->codeCount = count;
                 line->code = (uint16_t *)malloc(count * sizeof(uint16_t));
                 char *temp = strdup(line->operands);
                 char *token = strtok(temp, ",");
                 int idx = 0;
                 while(token) {
                     trim(token);
                     int val = parseImmediate(token);
                     line->code[idx++] = (uint16_t)val;
                     token = strtok(NULL, ",");
                 }
                 free(temp);
                 loc_data += count * 2;
             } else if(cmpIgnoreCase(line->mnemonic, ".space") == 0) {
                 int size = (int)strtol(line->operands, NULL, 0);
                 line->codeCount = 0; // no code produced
                 loc_data += size;
             } else if(cmpIgnoreCase(line->mnemonic, ".text") == 0 || cmpIgnoreCase(line->mnemonic, ".data") == 0) {
                 if(cmpIgnoreCase(line->mnemonic, ".text") == 0)
                     currentSection = SECTION_TEXT;
                 else
                     currentSection = SECTION_DATA;
             }
             continue;
         }
         if(line->mnemonic) {
             InstructionDef *inst = lookupInstruction(line->mnemonic);
             if(!inst) {
                 fprintf(stderr, "Error on line %d: Unknown mnemonic '%s'\n", line->lineNo, line->mnemonic);
                 exit(1);
             }
             uint16_t machineWord = 0;
             if(inst->type == INST_R) {
                 // R‑type: Expect two register operands.
                 // Special-case "jr" and "jalr": if only one operand is given, set second register to 0.
                 char *ops = line->operands;
                 if(!ops) {
                     fprintf(stderr, "Error on line %d: Missing operands for '%s'\n", line->lineNo, line->mnemonic);
                     exit(1);
                 }
                 char *token = strtok(ops, ", \t");
                 if(!token) {
                     fprintf(stderr, "Error on line %d: Expected register operand\n", line->lineNo);
                     exit(1);
                 }
                 int reg1 = parseRegister(token);
                 int reg2;
                 token = strtok(NULL, ", \t");
                 if(!token) {
                     // For jr and jalr, if second operand is missing, set reg2 = 0.
                     if(cmpIgnoreCase(inst->mnemonic, "jr") == 0 ||
                        cmpIgnoreCase(inst->mnemonic, "jalr") == 0) {
                         reg2 = 0;
                     } else {
                         fprintf(stderr, "Error on line %d: Expected second register operand\n", line->lineNo);
                         exit(1);
                     }
                 } else {
                     reg2 = parseRegister(token);
                 }
                 machineWord |= (inst->funct4 & 0xF) << 12;
                 machineWord |= (reg2 & 0x7) << 9;
                 machineWord |= (reg1 & 0x7) << 6;
                 machineWord |= (inst->funct3 & 0x7) << 3;
                 machineWord |= (inst->opcode & 0x7);
             } else if(inst->type == INST_I) {
                 // I‑type: Expect register, immediate.
                 char *ops = line->operands;
                 if(!ops) {
                     fprintf(stderr, "Error on line %d: Missing operands for '%s'\n", line->lineNo, line->mnemonic);
                     exit(1);
                 }
                 char *token = strtok(ops, ", \t");
                 if(!token) {
                     fprintf(stderr, "Error on line %d: Expected register operand\n", line->lineNo);
                     exit(1);
                 }
                 int reg = parseRegister(token);
                 token = strtok(NULL, ", \t");
                 if(!token) {
                     fprintf(stderr, "Error on line %d: Expected immediate operand\n", line->lineNo);
                     exit(1);
                 }
                 int imm = parseImmediate(token);
                 if(cmpIgnoreCase(inst->mnemonic, "srli") == 0) {
                     imm = (0x2 << 4) | (imm & 0xF);
                 } else if(cmpIgnoreCase(inst->mnemonic, "srai") == 0) {
                     imm = (0x4 << 4) | (imm & 0xF);
                 } else if(cmpIgnoreCase(inst->mnemonic, "slli") == 0) {
                     imm = (0x1 << 4) | (imm & 0xF);
                 }
                 machineWord |= ((imm & 0x7F) << 9);
                 machineWord |= ((reg & 0x7) << 6);
                 machineWord |= ((inst->funct3 & 0x7) << 3);
                 machineWord |= (inst->opcode & 0x7);
             } else if(inst->type == INST_B) {
                 // Branch instructions.
                 char *ops = line->operands;
                 if(!ops) {
                     fprintf(stderr, "Error on line %d: Missing operands for branch\n", line->lineNo);
                     exit(1);
                 }
                 int offset, rs1, rs2;
                 char *token = strtok(ops, ", \t");
                 if(cmpIgnoreCase(line->mnemonic, "bz") == 0 || cmpIgnoreCase(line->mnemonic, "bnz") == 0) {
                     // Single-register branch.
                     if(!token) {
                         fprintf(stderr, "Error on line %d: Expected register operand for branch\n", line->lineNo);
                         exit(1);
                     }
                     rs1 = parseRegister(token);
                     token = strtok(NULL, ", \t");
                     if(!token) {
                         fprintf(stderr, "Error on line %d: Expected label for branch\n", line->lineNo);
                         exit(1);
                     }
                     Symbol *sym = findSymbol(token);
                     if(!sym) {
                         fprintf(stderr, "Error on line %d: Undefined label '%s'\n", line->lineNo, token);
                         exit(1);
                     }
                     offset = (sym->address - (line->address)) >> 1; //Using exact current instruction's address
                     if(offset < -8 || offset > 7) {
                         fprintf(stderr, "Error on line %d: Branch offset out of range\n", line->lineNo);
                         exit(1);
                     }
                     rs2 = 0;
                     machineWord |= ((offset & 0xF) << 12);
                     machineWord |= ((rs2 & 0x7) << 9);
                     machineWord |= ((rs1 & 0x7) << 6);
                     machineWord |= ((inst->funct3 & 0x7) << 3);
                     machineWord |= (inst->opcode & 0x7);
                 } else {
                     // Two-register branch.
                     if(!token) {
                         fprintf(stderr, "Error on line %d: Expected first register operand for branch\n", line->lineNo);
                         exit(1);
                     }
                     rs1 = parseRegister(token);
                     token = strtok(NULL, ", \t");
                     if(!token) {
                         fprintf(stderr, "Error on line %d: Expected second register operand for branch\n", line->lineNo);
                         exit(1);
                     }
                     rs2 = parseRegister(token);
                     token = strtok(NULL, ", \t");
                     if(!token) {
                         fprintf(stderr, "Error on line %d: Expected label for branch\n", line->lineNo);
                         exit(1);
                     }
                     Symbol *sym = findSymbol(token);
                     if(!sym) {
                         fprintf(stderr, "Error on line %d: Undefined label '%s'\n", line->lineNo, token);
                         exit(1);
                     }
                     offset = (sym->address - (line->address)) >> 1;  //Fix offset calculations 
                     if(offset < -8 || offset > 7) {
                         fprintf(stderr, "Error on line %d: Branch offset out of range\n", line->lineNo);
                         exit(1);
                     }
                     machineWord |= ((offset & 0xF) << 12);
                     machineWord |= ((rs2 & 0x7) << 9);
                     machineWord |= ((rs1 & 0x7) << 6);
                     machineWord |= ((inst->funct3 & 0x7) << 3);
                     machineWord |= (inst->opcode & 0x7);
                 }
             } else if(inst->type == INST_L) {
                 // Load/Store instructions.
                 char *ops = line->operands;
                 if(!ops) {
                     fprintf(stderr, "Error on line %d: Missing operands for '%s'\n", line->lineNo, inst->mnemonic);
                     exit(1);
                 }
                 if(cmpIgnoreCase(inst->mnemonic, "lb") == 0 ||
                    cmpIgnoreCase(inst->mnemonic, "lw") == 0 ||
                    cmpIgnoreCase(inst->mnemonic, "lbu") == 0) {
                     // Load: format: rd, offset(rs)
                     char *token = strtok(ops, ", \t");
                     if(!token) {
                         fprintf(stderr, "Error on line %d: Expected destination register for load\n", line->lineNo);
                         exit(1);
                     }
                     int rd = parseRegister(token);
                     token = strtok(NULL, ", \t");
                     if(!token) {
                         fprintf(stderr, "Error on line %d: Expected memory operand for load\n", line->lineNo);
                         exit(1);
                     }
                     char *parenOpen = strchr(token, '(');
                     char *parenClose = strchr(token, ')');
                     if(!parenOpen || !parenClose) {
                         fprintf(stderr, "Error on line %d: Memory operand format error, expected offset(register)\n", line->lineNo);
                         exit(1);
                     }
                     *parenOpen = '\0';
                     int imm = parseImmediate(token);
                     char *regStr = parenOpen + 1;
                     *parenClose = '\0';
                     int rs = parseRegister(regStr);
                     machineWord |= ((imm & 0xF) << 12);
                     machineWord |= ((rs & 0x7) << 9);
                     machineWord |= ((rd & 0x7) << 6);
                     machineWord |= ((inst->funct3 & 0x7) << 3);
                     machineWord |= (inst->opcode & 0x7);
                 } else if(cmpIgnoreCase(inst->mnemonic, "sb") == 0 ||
                           cmpIgnoreCase(inst->mnemonic, "sw") == 0) {
                     // Store: format: rs2, offset(rs1)
                     char *token = strtok(ops, ", \t");
                     if(!token) {
                         fprintf(stderr, "Error on line %d: Expected source register for store\n", line->lineNo);
                         exit(1);
                     }
                     int rs2 = parseRegister(token);
                     token = strtok(NULL, ", \t");
                     if(!token) {
                         fprintf(stderr, "Error on line %d: Expected memory operand for store\n", line->lineNo);
                         exit(1);
                     }
                     char *parenOpen = strchr(token, '(');
                     char *parenClose = strchr(token, ')');
                     if(!parenOpen || !parenClose) {
                         fprintf(stderr, "Error on line %d: Memory operand format error, expected offset(register)\n", line->lineNo);
                         exit(1);
                     }
                     *parenOpen = '\0';
                     int imm = parseImmediate(token);
                     char *regStr = parenOpen + 1;
                     *parenClose = '\0';
                     int rs1 = parseRegister(regStr);
                     machineWord |= ((imm & 0xF) << 12);
                     machineWord |= ((rs2 & 0x7) << 9);
                     machineWord |= ((rs1 & 0x7) << 6);
                     machineWord |= ((inst->funct3 & 0x7) << 3);
                     machineWord |= (inst->opcode & 0x7);
                 } else {
                     fprintf(stderr, "Error on line %d: Unknown load/store mnemonic '%s'\n", line->lineNo, inst->mnemonic);
                     exit(1);
                 }
             } else if(inst->type == INST_J) {
                 // J‑type: PC‑relative jump.
                 // Format: f | imm[9:4] | rd | imm[3:1] | opcode.
                 if(line->operands == NULL) {
                     fprintf(stderr, "Error on line %d: Missing operand for jump\n", line->lineNo);
                     exit(1);
                 }
                 char *token = strtok(line->operands, ", \t");
                 int rd = 0;
                 if(cmpIgnoreCase(inst->mnemonic, "jal") == 0) {
                     if(!token) {
                         fprintf(stderr, "Error on line %d: Expected register operand for jump\n", line->lineNo);
                         exit(1);
                     }
                     rd = parseRegister(token);
                     token = strtok(NULL, ", \t");
                 }
                if(!token) {
                    fprintf(stderr, "Error on line %d: Expected label for jump\n", line->lineNo);
                    exit(1);
                }
                 Symbol *sym = findSymbol(token);
                 if(!sym) {
                     fprintf(stderr, "Error on line %d: Undefined label '%s'\n", line->lineNo, token);
                     exit(1);
                 }
                 int currPC = line->address;
                 int targetPC = sym->address;
                 int offset = (targetPC - currPC);
                 if(offset < -128 || offset > 127) {
                     fprintf(stderr, "Error on line %d: Jump offset out of range\n", line->lineNo);
                     exit(1);
                 }
                 int offset3To1 = (offset >> 1) & 0x7;
                 int offset9To4 = (offset >> 4) & 0x3F;
                 int f = (cmpIgnoreCase(inst->mnemonic, "jal") == 0) ? 1 : 0;
                 machineWord |= (f & 0x1) << 15;
                 machineWord |= ((offset9To4) << 9);
                 machineWord |= ((rd & 0x7) << 6);
                 machineWord |= ((offset3To1) << 3);
                 machineWord |= (inst->opcode & 0xF);
             } else if(inst->type == INST_U) {
                 // U‑type: Format: f | imm[15:10] | rd | imm[9:7] | opcode.
                 char *ops = line->operands;
                 char *token = strtok(ops, ", \t");
                 if(!token) {
                     fprintf(stderr, "Error on line %d: Expected register for U‑type instruction\n", line->lineNo);
                     exit(1);
                 }
                 int rd = parseRegister(token);
                 token = strtok(NULL, ", \t");
                 if(!token) {
                     fprintf(stderr, "Error on line %d: Expected immediate for U‑type instruction\n", line->lineNo);
                     exit(1);
                 }

                 int imm_val = parseImmediate(token);
                 int f = (cmpIgnoreCase(inst->mnemonic, "auipc") == 0) ? 1 : 0;  //Differentiate

                 int upper = (imm_val >> 3) & 0x3F;  // bits for imm[15:10]
                 int lower = imm_val & 0x7;          // bits for imm[9:7]
                 machineWord |= (f & 0x1) << 15;   //Store f
                 machineWord |= (upper << 9);
                 machineWord |= ((rd & 0x7) << 6);
                 machineWord |= (lower << 3);
                 machineWord |= (inst->opcode & 0x7);

             } else if(inst->type == INST_S) {
                 // System instructions.
                 if(line->operands == NULL) {
                     fprintf(stderr, "Error on line %d: ecall missing operand\n", line->lineNo);
                     exit(1);
                 }
                 int svc = parseImmediate(line->operands);
                 machineWord = (svc << 6) | 0x7;
             }
             line->codeCount = 1;
             line->code = (uint16_t *)malloc(sizeof(uint16_t));
             line->code[0] = machineWord;
             loc_text += 2;
             line->elementSize = 2;
         }
     }
 }

 // -----------------------
 // Listing File Generation (.lst)
 // -----------------------

 void generateListing(const char *sourceFilename) {
     char listingFilename[256];
     strcpy(listingFilename, sourceFilename);
     char *dot = strrchr(listingFilename, '.');
     if(dot)
         strcpy(dot, ".lst");
     else
         strcat(listingFilename, ".lst");
     FILE *lst = fopen(listingFilename, "w");
     if(!lst) {
         perror("Error opening listing file");
         exit(1);
     }
     fprintf(lst, "Line   Address   Machine Code    Source\n");
     fprintf(lst, "-----------------------------------------------------\n");
     for (int i = 0; i < lineCount; i++) {
         Line *l = lines[i];
         if(l->section == SECTION_TEXT)
             fprintf(lst, "%4d   0x%04X   ", l->lineNo, l->address);
         else if(l->section == SECTION_DATA)
             fprintf(lst, "%4d   0x%04X   ", l->lineNo, l->address);
         else
             fprintf(lst, "%4d           ", l->lineNo);
         if(l->codeCount > 0) {
             for (int j = 0; j < l->codeCount; j++)
                 fprintf(lst, "%0*X ", (l->elementSize==1)?2:4, l->code[j]);
             int pad = 12 - (l->codeCount * ((l->elementSize==1)?3:5));
             for (int k = 0; k < pad; k++) fprintf(lst, " ");
         } else {
             fprintf(lst, "              ");
         }
         fprintf(lst, " %s", l->original);
     }
     fclose(lst);
     printf("Listing file generated: %s\n", listingFilename);
 }

 // -----------------------
 // Dump Binary: Write Memory Image to Output File
 // -----------------------

 void dumpBinary(const char *binFilename) {
     int maxAddr = 0;
     for (int i = 0; i < lineCount; i++) {
         if (lines[i]->codeCount > 0) {
             int endAddr = lines[i]->address + lines[i]->codeCount * lines[i]->elementSize;
             if(endAddr > maxAddr)
                 maxAddr = endAddr;
         }
     }
     if(maxAddr == 0)
         maxAddr = 1;  // write at least one byte

     unsigned char *memoryImage = (unsigned char *)calloc(maxAddr, 1);
     if(!memoryImage) {
          perror("calloc");
          exit(1);
     }
     // Copy each line's code into the memory image at its computed address.
     for (int i = 0; i < lineCount; i++) {
          Line *l = lines[i];
          if(l->codeCount > 0 && (l->section == SECTION_TEXT || l->section == SECTION_DATA)) {
              for (int j = 0; j < l->codeCount; j++) {
                  int addr = l->address + j * l->elementSize;
                  if(l->elementSize == 1) {
                      memoryImage[addr] = l->code[j] & 0xFF;
                  } else if(l->elementSize == 2) {
                      memoryImage[addr] = l->code[j] & 0xFF;
                      memoryImage[addr+1] = (l->code[j] >> 8) & 0xFF;
                  }
              }
          }
     }
     FILE *fp = fopen(binFilename, "wb");
     if(!fp) {
          perror("Error opening binary file for writing");
          exit(1);
     }
     fwrite(memoryImage, 1, maxAddr, fp);
     fclose(fp);
     free(memoryImage);
     printf("Binary file generated: %s\n", binFilename);
 }

 // -----------------------
 // Verbose Dump: Symbol Table and Memory Usage
 // -----------------------

 void dumpVerbose() {
     printf("\n--- Symbol Table ---\n");
     Symbol *cur = symbolTable;
     while(cur) {
         printf("%-10s  0x%04X  %s\n", cur->name, cur->address,
                (cur->section==SECTION_TEXT) ? "TEXT" : (cur->section==SECTION_DATA ? "DATA" : "NONE"));
         cur = cur->next;
     }
     printf("\nMemory usage:\n");
     printf("  Text section: %d bytes\n", loc_text);
     printf("  Data section: %d bytes\n", loc_data);
 }

 // -----------------------
 // Main Function and Command-Line Argument Parsing
 // -----------------------

 int main(int argc, char **argv) {
     int verbose = 0;
     int debugModeFlag = 0;
     char *filename = NULL;
     char *binFilename = NULL;
     
     if(argc < 2) {
         fprintf(stderr, "Usage: %s [-v] [-d] [-o <binary_file>] <sourcefile>\n", argv[0]);
         exit(1);
     }
     for (int i = 1; i < argc; i++) {
         if(strcmp(argv[i], "-v") == 0)
             verbose = 1;
         else if(strcmp(argv[i], "-d") == 0)
             debugModeFlag = 1;
         else if(strcmp(argv[i], "-o") == 0) {
             if(i + 1 < argc) {
                 binFilename = argv[i+1];
                 i++;
             } else {
                 fprintf(stderr, "Error: -o switch requires a binary file name\n");
                 exit(1);
             }
         } else {
             filename = argv[i];
         }
     }
     if(filename == NULL) {
         fprintf(stderr, "Error: No source file specified.\n");
         exit(1);
     }
     // If no binary file name provided, derive it from the source file name by replacing its extension with ".bin".
     if(binFilename == NULL) {
         char temp[256];
         strcpy(temp, filename);
         char *dot = strrchr(temp, '.');
         if(dot)
             strcpy(dot, ".bin");
         else
             strcat(temp, ".bin");
         binFilename = strdup(temp);
     }
     
     FILE *fp = fopen(filename, "r");
     if(!fp) {
         perror("Error opening source file");
         exit(1);
     }
     
     currentSection = SECTION_NONE;
     if(debugModeFlag)
         printf("Debug: Starting Pass 1\n");
     pass1(fp);
     if(debugModeFlag)
         printf("Debug: Pass 1 complete, %d lines processed\n", lineCount);
     if(debugModeFlag)
         printf("Debug: Starting Pass 2\n");
     pass2();
     if(debugModeFlag)
         printf("Debug: Pass 2 complete\n");
     
     generateListing(filename);
     dumpBinary(binFilename);
     if(verbose)
         dumpVerbose();
     
     for (int i = 0; i < lineCount; i++)
         freeLine(lines[i]);
     while(symbolTable) {
         Symbol *temp = symbolTable;
         symbolTable = symbolTable->next;
         free(temp);
     }
     if(binFilename)
         free(binFilename);
     
     return 0;
 }
 
