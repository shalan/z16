.text
    .org    0
main:
    li      a0, 0x55           
    xori    a0, 0x0F       
    ecall   1                 

    ecall   3               