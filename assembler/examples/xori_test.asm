    .text
    .globl _start

_start:
    li x5, 4      
    xori x5,1
                     
    li a0, 10
    ecall 3           
