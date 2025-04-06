    .text
    .globl _start

_start:
    li x5, 4
    li x4, 4      
    xor x5,x4
                     
    li a0, 10
    ecall 3           
