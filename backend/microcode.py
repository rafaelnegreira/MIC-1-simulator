REG_PC = 0
REG_AC = 1
REG_SP = 2
REG_IR = 3
REG_TIR = 4
REG_ZERO = 5
REG_POS1 = 6
REG_NEG1 = 7
REG_AMASK = 8
REG_SMASK = 9
REG_A = 10 

ALU_ADD = 0b00
ALU_AND = 0b01
ALU_PASS_A = 0b10
ALU_INV_A = 0b11

SHIFT_NO = 0b00
SHIFT_RIGHT = 0b01
SHIFT_LEFT = 0b10

COND_NO = 0b00
COND_N = 0b01
COND_Z = 0b10
COND_ALWAYS = 0b11

def make_inst(addr_jump, bus_a, bus_b, bus_c, enc, wr, rd, mar, mbr, sh, alu, cond, amux):
    """Constrói palavra de 32 bits (MIR)"""
    word = 0
    word |= (addr_jump & 0xFF) << 0
    word |= (bus_a & 0xF) << 8
    word |= (bus_b & 0xF) << 12
    word |= (bus_c & 0xF) << 16
    word |= (enc & 0x1) << 20
    word |= (wr & 0x1) << 21
    word |= (rd & 0x1) << 22
    word |= (mar & 0x1) << 23
    word |= (mbr & 0x1) << 24
    word |= (sh & 0x3) << 25
    word |= (alu & 0x3) << 27
    word |= (cond & 0x3) << 29
    word |= (amux & 0x1) << 31
    return word

CONTROL_STORE = [0] * 512

# MICROPROGRAMA (Baseado no MIC-1 Tanenbaum)

# --- BUSCA (FETCH) ---
# 0: MAR = PC; RD
CONTROL_STORE[0] = make_inst(0, REG_ZERO, REG_PC, 0, 0, 0, 1, 1, 0, SHIFT_NO, ALU_ADD, COND_NO, 0)
# 1: PC = PC + 1; RD
CONTROL_STORE[1] = make_inst(0, REG_POS1, REG_PC, REG_PC, 1, 0, 1, 0, 0, SHIFT_NO, ALU_ADD, COND_NO, 0)
# 2: IR = MBR; if N goto 28 (Bit mais significativo do Opcode)
CONTROL_STORE[2] = make_inst(28, 0, 0, REG_IR, 1, 0, 0, 0, 0, SHIFT_NO, ALU_PASS_A, COND_N, 1)

# ==============================================================================
# RAMO ESQUERDO (Bit 15 = 0) - Instruções 0xxx (LODD, STOD, ADDD...)
# ==============================================================================
# 3: TIR = LSHIFT(IR + IR); if N goto 19 (Separa 0xxx de 1xxx)
CONTROL_STORE[3] = make_inst(19, REG_IR, REG_IR, REG_TIR, 1, 0, 0, 0, 0, SHIFT_LEFT, ALU_ADD, COND_N, 0)

# 4: TIR = LSHIFT(TIR); if N goto 11 (Separa 00xx de 01xx)
CONTROL_STORE[4] = make_inst(11, REG_ZERO, REG_TIR, REG_TIR, 1, 0, 0, 0, 0, SHIFT_LEFT, ALU_ADD, COND_N, 0)

# 5: ALU = TIR; if N goto 9 (Separa 0000 LODD de 0001 STOD)
CONTROL_STORE[5] = make_inst(9, REG_ZERO, REG_TIR, 0, 0, 0, 0, 0, 0, SHIFT_NO, ALU_ADD, COND_N, 0)

# 11: ALU = TIR; if N goto 25 (Separa 010x de 011x)
CONTROL_STORE[11] = make_inst(25, REG_ZERO, REG_TIR, 0, 0, 0, 0, 0, 0, SHIFT_NO, ALU_ADD, COND_N, 0)

# 19: TIR = LSHIFT(TIR); if N goto 25 (Separa sub-grupos do 0xxx) 
CONTROL_STORE[19] = make_inst(25, REG_ZERO, REG_TIR, REG_TIR, 1, 0, 0, 0, 0, SHIFT_LEFT, ALU_ADD, COND_N, 0)

# 25: ALU = TIR; if N goto 27 (Separa JUMP 0110 de LOCO 0111)
CONTROL_STORE[25] = make_inst(27, REG_ZERO, REG_TIR, 0, 0, 0, 0, 0, 0, SHIFT_NO, ALU_ADD, COND_N, 0)


# ==============================================================================
# RAMO DIREITO (Bit 15 = 1) - Instruções 1xxx (LODL, PUSH, POP...)
# ==============================================================================
# 28: TIR = LSHIFT(IR + IR); if N goto 40 (Separa 10xx de 11xx) 
CONTROL_STORE[28] = make_inst(40, REG_IR, REG_IR, REG_TIR, 1, 0, 0, 0, 0, SHIFT_LEFT, ALU_ADD, COND_N, 0)

# 29: TIR = LSHIFT(TIR); if N goto 35 (Separa 100x [LODL/STOL] de 101x [ADDL/SUBL])
CONTROL_STORE[29] = make_inst(35, REG_ZERO, REG_TIR, REG_TIR, 1, 0, 0, 0, 0, SHIFT_LEFT, ALU_ADD, COND_N, 0)

# 30: ALU = TIR; if N goto 33 (Separa LODL 1000 de STOL 1001)
CONTROL_STORE[30] = make_inst(33, REG_ZERO, REG_TIR, 0, 0, 0, 0, 0, 0, SHIFT_NO, ALU_ADD, COND_N, 0)

# 35: ALU = TIR; if N goto 38 (Separa ADDL 1010 de SUBL 1011)
CONTROL_STORE[35] = make_inst(38, REG_ZERO, REG_TIR, 0, 0, 0, 0, 0, 0, SHIFT_NO, ALU_ADD, COND_N, 0)

# 40: TIR = LSHIFT(TIR); if N goto 46 (Separa 100x/101x de 11xx) 
CONTROL_STORE[40] = make_inst(46, REG_ZERO, REG_TIR, REG_TIR, 1, 0, 0, 0, 0, SHIFT_LEFT, ALU_ADD, COND_N, 0)

# 41: ALU = TIR; if N goto 44 (Decodifica 10xx -> LODL, STOL, ADDL, SUBL) 
CONTROL_STORE[41] = make_inst(44, REG_ZERO, REG_TIR, 0, 0, 0, 0, 0, 0, SHIFT_NO, ALU_ADD, COND_N, 0)

# 46: TIR = LSHIFT(TIR); if N goto 50 (Separa 110x de 111x) 
CONTROL_STORE[46] = make_inst(50, REG_ZERO, REG_TIR, REG_TIR, 1, 0, 0, 0, 0, SHIFT_LEFT, ALU_ADD, COND_N, 0)

# 50: TIR = LSHIFT(TIR); if N goto 65 (Separa 1110 CALL de 1111 xxxx) [cite: 2]
CONTROL_STORE[50] = make_inst(65, REG_ZERO, REG_TIR, REG_TIR, 1, 0, 0, 0, 0, SHIFT_LEFT, ALU_ADD, COND_N, 0)

# 51: TIR = LSHIFT(TIR); if N goto 59 (Decodifica dentro de 1111 xxxx) [cite: 2]
CONTROL_STORE[51] = make_inst(59, REG_ZERO, REG_TIR, REG_TIR, 1, 0, 0, 0, 0, SHIFT_LEFT, ALU_ADD, COND_N, 0)

# 52: ALU = TIR; if N goto 56 (Separa PSHI de POPI) [cite: 2]
CONTROL_STORE[52] = make_inst(56, REG_ZERO, REG_TIR, 0, 0, 0, 0, 0, 0, SHIFT_NO, ALU_ADD, COND_N, 0)

# 59: ALU = TIR; if N goto 62 (Separa PUSH 11110100 de POP 11110110) [cite: 2]
CONTROL_STORE[59] = make_inst(62, REG_ZERO, REG_TIR, 0, 0, 0, 0, 0, 0, SHIFT_NO, ALU_ADD, COND_N, 0)

# 65: TIR = LSHIFT(TIR); if N goto 73 (Separa RETN/SWAP de INSP/DESP) [cite: 2]
CONTROL_STORE[65] = make_inst(73, REG_ZERO, REG_TIR, REG_TIR, 1, 0, 0, 0, 0, SHIFT_LEFT, ALU_ADD, COND_N, 0)

# ==============================================================================
# IMPLEMENTAÇÃO DAS INSTRUÇÕES
# ==============================================================================

# --- LODD (0000) ---
CONTROL_STORE[6] = make_inst(0, REG_ZERO, REG_IR, 0, 0, 0, 1, 1, 0, SHIFT_NO, ALU_ADD, COND_NO, 0) # MAR=IR; RD
CONTROL_STORE[7] = make_inst(0, 0, 0, 0, 0, 0, 1, 0, 0, SHIFT_NO, 0, 0, 0) # RD (Wait)
CONTROL_STORE[8] = make_inst(0, 0, 0, REG_AC, 1, 0, 0, 0, 0, SHIFT_NO, ALU_PASS_A, COND_ALWAYS, 1) # AC=MBR; Goto 0

# --- STOD (0001) ---
CONTROL_STORE[9] = make_inst(0, REG_AC, REG_IR, 0, 0, 1, 0, 1, 1, SHIFT_NO, ALU_PASS_A, COND_NO, 0) # MAR=IR; MBR=AC; WR
CONTROL_STORE[10] = make_inst(0, 0, 0, 0, 0, 1, 0, 0, 0, SHIFT_NO, 0, COND_ALWAYS, 0) # WR; Goto 0

# --- ADDD (0010) ---
CONTROL_STORE[12] = make_inst(0, REG_ZERO, REG_IR, 0, 0, 0, 1, 1, 0, SHIFT_NO, ALU_ADD, COND_NO, 0) # MAR=IR; RD
CONTROL_STORE[13] = make_inst(0, 0, 0, 0, 0, 0, 1, 0, 0, SHIFT_NO, 0, 0, 0) # RD
# AC = AC + MBR; Goto 0

CONTROL_STORE[14] = make_inst(0, REG_AC, REG_AC, REG_AC, 1, 0, 0, 0, 0, SHIFT_NO, ALU_ADD, COND_ALWAYS, 1)
# --- LOCO (0111) ---
CONTROL_STORE[27] = make_inst(0, REG_AMASK, REG_IR, REG_AC, 1, 0, 0, 0, 0, SHIFT_NO, ALU_AND, COND_ALWAYS, 0) # AC=IR&AMASK

# --- LODL (1000) - Load Local ---
# 31: A = SP + IR; Goto 32 
CONTROL_STORE[31] = make_inst(32, REG_SP, REG_IR, REG_A, 1, 0, 0, 0, 0, SHIFT_NO, ALU_ADD, COND_ALWAYS, 0)

# 32: MAR = A; RD; Goto 7
CONTROL_STORE[32] = make_inst(7, REG_ZERO, REG_A, 0, 0, 0, 1, 1, 0, SHIFT_NO, ALU_ADD, COND_ALWAYS, 0)

# --- ADDL (1010) - Add Local ---
# 36: A = SP + IR; Goto 37 
CONTROL_STORE[36] = make_inst(37, REG_SP, REG_IR, REG_A, 1, 0, 0, 0, 0, SHIFT_NO, ALU_ADD, COND_ALWAYS, 0)

# 37: MAR = A; RD; Goto 13 
CONTROL_STORE[37] = make_inst(13, REG_ZERO, REG_A, 0, 0, 0, 1, 1, 0, SHIFT_NO, ALU_ADD, COND_ALWAYS, 0)

# --- PUSH (1111 0100) ---
# Caminho: 2 -> 28 -> 40 -> 46 -> 50 -> 51 -> 59 -> 60
# 60: SP = SP - 1 [cite: 2]
CONTROL_STORE[60] = make_inst(0, REG_NEG1, REG_SP, REG_SP, 1, 0, 0, 0, 0, SHIFT_NO, ALU_ADD, COND_NO, 0)
# 61: MAR = SP; MBR = AC; WR; Goto 10 (Reaproveita final de STOD) [cite: 2]
CONTROL_STORE[61] = make_inst(10, REG_AC, REG_SP, 0, 0, 1, 0, 1, 1, SHIFT_NO, ALU_PASS_A, COND_ALWAYS, 0)

# --- POP (1111 0110) ---
# 62: MAR = SP; SP = SP + 1; RD [cite: 2]
CONTROL_STORE[62] = make_inst(0, REG_POS1, REG_SP, REG_SP, 1, 0, 1, 1, 0, SHIFT_NO, ALU_ADD, COND_NO, 0)
# 63: RD (Wait) [cite: 2]
CONTROL_STORE[63] = make_inst(0, 0, 0, 0, 0, 0, 1, 0, 0, SHIFT_NO, 0, 0, 0)
# 64: AC = MBR; Goto 0 [cite: 2]
CONTROL_STORE[64] = make_inst(0, 0, 0, REG_AC, 1, 0, 0, 0, 0, SHIFT_NO, ALU_PASS_A, COND_ALWAYS, 1)

# Instrução JUMP (para loops funcionarem)
CONTROL_STORE[26] = make_inst(0, REG_AMASK, REG_IR, REG_PC, 1, 0, 0, 0, 0, SHIFT_NO, ALU_AND, COND_ALWAYS, 0)

# 11: ALU = TIR; if N goto 15 (Separa 0010 ADDD de 0011 SUBD)
CONTROL_STORE[11] = make_inst(15, REG_ZERO, REG_TIR, 0, 0, 0, 0, 0, 0, SHIFT_NO, ALU_ADD, COND_N, 0)

# Implementação de SUBD (AC = AC - MBR) -> AC = AC + 1 + INV(MBR)
# 15: MAR = IR; RD
CONTROL_STORE[15] = make_inst(0, REG_ZERO, REG_IR, 0, 0, 0, 1, 1, 0, SHIFT_NO, ALU_ADD, COND_NO, 0)
# 16: AC = AC + 1; RD (Wait)
CONTROL_STORE[16] = make_inst(0, REG_POS1, REG_AC, REG_AC, 1, 0, 1, 0, 0, SHIFT_NO, ALU_ADD, COND_NO, 0)
# 17: A = INV(MBR)
CONTROL_STORE[17] = make_inst(0, REG_ZERO, 0, REG_A, 1, 0, 0, 0, 1, SHIFT_NO, ALU_INV_A, COND_NO, 1) # AMUX=1(MBR) -> INV(MBR)
# 18: AC = AC + A; Goto 0
CONTROL_STORE[18] = make_inst(0, REG_A, REG_AC, REG_AC, 1, 0, 0, 0, 0, SHIFT_NO, ALU_ADD, COND_ALWAYS, 0)

# --- JNZE (1101) ---
# Caminho: 2 -> 28 -> 40 -> 41 -> 44
# 41: ALU = TIR; if N goto 44 (Separa 10xx de 110x)
CONTROL_STORE[41] = make_inst(44, REG_ZERO, REG_TIR, 0, 0, 0, 0, 0, 0, SHIFT_NO, ALU_ADD, COND_N, 0)

# 44: ALU = AC; if Z goto 0 
CONTROL_STORE[44] = make_inst(0, REG_AC, REG_ZERO, 0, 0, 0, 0, 0, 0, SHIFT_NO, ALU_PASS_A, COND_Z, 0)
# 45: PC = BAND(IR, AMASK); Goto 0 (Pula)
CONTROL_STORE[45] = make_inst(0, REG_AMASK, REG_IR, REG_PC, 1, 0, 0, 0, 0, SHIFT_NO, ALU_AND, COND_ALWAYS, 0)