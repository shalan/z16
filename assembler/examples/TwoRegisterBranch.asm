.text
.org 0
main:
li a0, 10 # Load immediate 10 into a0
li a1, 10 # Load immediate 10 into a1
beq a0, a1, equal_case # Branch if a0 == a1
j end # Unconditional jump

equal_case:
li t0, 1 # If equal, set t0 = 1

end:
ecall 3 # Terminate program
