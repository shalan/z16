.org 0x0000
.text
start:
    ; Initialize stack pointer
    lui sp, 0x10         ; Load upper 10 bits of 0x1000
    addi sp, 0x00    ; sp = 0x1000
    
    ; Test U-type instructions
    lui a0, 0x1234       ; Load upper immediate
    auipc a1, 0x00       ; Add upper immediate to PC
    
    ; Test I-type arithmetic
    addi t0, 15      ; t0 = 15 (LI pseudo-instruction)
    addi s0, -20     ; s0 = -20
    slti t1, 0       ; Set less than immediate (should be 1)
    andi a0, 0xFF    ; Mask lower 8 bits
    
    ; Test R-type operations
    mv t1, t0            ; Copy register (pseudo-instruction)
    add s0, t1       ; 15 + 15 = 30
    sub s1, s0       ; 0 - 30 = -30
    xor a1, s0       ; Bitwise XOR
    
    ; Test memory operations (S/L-type)
    sw t0, 0(sp)         ; Store to stack
    lw a0, 0(sp)        ; Load from stack
    addi sp, -4     ; Adjust stack
    
    ; Test pseudo-instructions
    li t0, 0xABCD       ; Load immediate (pseudo: lui + addi)
    
    ; Test control flow
    jal ra, subroutine  ; Call subroutine
    beq a0, t0, test_branches
    
test_branches:
    ; Test B-type instructions
    addi x0, 10
    addi t1, 10
    beq t0, t1, branch_eq    ; Should jump
    
loop:
    addi t0, -1
    bnz t0, loop          ; Loop 10 times
    
    ; Test various branch conditions
    blt s0, x0, branch_lt  ; -30 < 0
    
    ; Test J-type jumps
    j end
    
branch_eq:
    addi a1, 1
    j test_branches
    
branch_lt:
    addi a1, 2
    j test_branches
    
subroutine:
    ; Test stack operations
    addi sp, -8
    sw s0, 4(sp)        ; Save callee-saved
    sw s1, 0(sp)
    
    ; Test argument registers
    addi a0, 5
    addi a1, 3
    jal ra, multiply
    
    ; Restore registers
    lw s1, 0(sp)
    lw s0, 4(sp)
    addi sp, 8
    jr ra               ; Return
    
multiply:
    ; Simple multiplication using adds
    addi t0, 0
    addi t1, 0
    addi a0, 0
mult_loop:
    bz t1, mult_end
    add a0, a1
    addi t1, -1
    j mult_loop
mult_end:
    jr ra
    
error:
    ; Error handler
    lui t0, 0xDEAD
    addi t0, 0xBEEF
    
end:
    ; System call to terminate
    ecall 3
