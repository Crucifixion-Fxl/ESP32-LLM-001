    .text
    .align 4
    .global bitlinear_forward_q_asm
    .type   bitlinear_forward_q_asm, @function

# 修复版 v2 —— 基于车道级单测定的事实：
#   1) ee.vmulas.s8.accx 每次只消耗寄存器的低 32 位（4 车道）
#   2) ee.movi.32.q q, ar, imm 是整体覆写：q = ar 放到 (3-imm)*32 位、其余清零
#      （imm=3 → 低 32 位，正好是 vmulas 消耗的窗口）
#   3) 原版的 bug：四次 movi 写同一个 q1 互相清零 → 75% 权重丢失，
#      幸存的 byte3 还和车道 0-3 错位配对
# 正确习语：8 个 Q 寄存器各装一个 32 位字，打 4 发 vmulas
#
# a2: x_vec(int8*), a3: packed_w_row(u8*), a4: length

bitlinear_forward_q_asm:
    entry a1, 64

    .literal_position
    movi    a5, LUT_UNPACK_W

    srli    a4, a4, 4                 # 外层循环次数 = length / 16

    ee.zero.accx

    beqz    a4, .L_dot_end

.L_dot_loop:
    # ---- x 的四个 32 位字 ----
    l32i    a6, a2, 0
    l32i    a7, a2, 4
    l32i    a8, a2, 8
    l32i    a9, a2, 12
    addi    a2, a2, 16

    ee.movi.32.q    q0, a6, 3         # q0 低 32 位 = x[0..3]
    ee.movi.32.q    q1, a7, 3         # q1 低 32 位 = x[4..7]
    ee.movi.32.q    q2, a8, 3         # q2 低 32 位 = x[8..11]
    ee.movi.32.q    q3, a9, 3         # q3 低 32 位 = x[12..15]

    # ---- w 的四个字节 -> LUT 解包 -> 四个 32 位字 ----
    l8ui    a6, a3, 0
    l8ui    a7, a3, 1
    l8ui    a8, a3, 2
    l8ui    a9, a3, 3
    addi    a3, a3, 4

    slli    a6, a6, 2
    add     a6, a5, a6
    l32i    a6, a6, 0
    ee.movi.32.q    q4, a6, 3         # q4 低 32 位 = 槽 0-3

    slli    a7, a7, 2
    add     a7, a5, a7
    l32i    a7, a7, 0
    ee.movi.32.q    q5, a7, 3         # q5 低 32 位 = 槽 4-7

    slli    a8, a8, 2
    add     a8, a5, a8
    l32i    a8, a8, 0
    ee.movi.32.q    q6, a8, 3         # q6 低 32 位 = 槽 8-11

    slli    a9, a9, 2
    add     a9, a5, a9
    l32i    a9, a9, 0
    ee.movi.32.q    q7, a9, 3         # q7 低 32 位 = 槽 12-15

    # ---- 四发 4 车道 MAC ----
    ee.vmulas.s8.accx   q0, q4        # x[0..3]  × w[0..3]
    ee.vmulas.s8.accx   q1, q5        # x[4..7]  × w[4..7]
    ee.vmulas.s8.accx   q2, q6        # x[8..11] × w[8..11]
    ee.vmulas.s8.accx   q3, q7        # x[12..15]× w[12..15]

    addi    a4, a4, -1
    bnez    a4, .L_dot_loop

.L_dot_end:
    movi     a2, 0
    ee.srs.accx a2, a2, 0

    retw
    .size bitlinear_forward_q_asm, . - bitlinear_forward_q_asm
