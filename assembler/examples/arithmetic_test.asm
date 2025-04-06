.text
    .org 0x0000
    li x5, 4
    li x4, 4      
    xor x5,x4
    li a0, string
    ecall 5 
    ecall 1 
    ecall 3
.data
    .org 0x0016
string:
    .asciiz "Hello, Z16!"