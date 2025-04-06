.text
    .globl _start

_start:
    j   target
    addi x1, 3       
    add x1, x3
   
target: jal x0, exit     
        sub x4, x6   

exit:   mv  x0, x0       
    ecall 3