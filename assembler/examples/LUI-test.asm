.text
.org 0
main:
    lui a0, %hi(w)
    addi a0, %lo(w) # Load address 0x100 into a0
    ecall 1
    lw t1, 0(a0) # Load word from memory address in a0 into t1
    lb t0, 2(a0) # Load byte from memory address a0 + 2 into t0
    mv a0, t1
    ecall 1
    ecall 3
    sw t1, 4(a0) # Store word t1 into memory at a0 + 4
    sb t0, 6(a0) # Store byte t0 into memory at a0 + 6
    ecall 3 # Terminate program

.data
.org 0x100
    w: .word 12
    b: .byte 0xAA