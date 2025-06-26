.text
.org 0x0020
    addi x1, 63      # ✅ valid
    addi x1, -64     # ✅ valid
    addi x1, 64      # ❌ should raise error
    addi x1, -65     # ❌ should raise error
