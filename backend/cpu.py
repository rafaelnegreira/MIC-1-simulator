import time
import ctypes
from .components import Register, ALU, Shifter, Memory, Amux
from .microcode import CONTROL_STORE

# --- MAPA DE TRADUÇÃO (Micro-Assembly) ---
MICRO_MNEMONICS = {
    # Busca (Fetch)
    0: "mar:=pc; rd;",
    1: "pc:=pc + 1; rd;",
    2: "ir:=mbr; if n then goto 28;",
    
    # Decodificação (Decode)
    3: "tir:=lshift(ir + ir); if n then goto 19;",
    4: "tir:=lshift(tir); if n then goto 11;",
    5: "alu:=tir; if n then goto 9;",
    
    # LODD (0000)
    6: "mar:=ir; rd;",
    7: "rd;",
    8: "ac:=mbr; goto 0;",
    
    # STOD (0001)
    9: "mar:=ir; mbr:=ac; wr;",
    10: "wr; goto 0;",
    
    # ADDD (0010)
    12: "mar:=ir; rd;",
    13: "rd;",
    14: "ac:=ac + mbr; goto 0;",
    
    # SUBD (0011)
    11: "alu:=tir; if n then goto 15;", # Decode step
    15: "mar:=ir; rd;",
    16: "ac:=ac + 1; rd;",
    17: "a:=inv(mbr);",
    18: "ac:=ac + a; goto 0;",
    
    # Árvore de Decodificação Estendida
    19: "tir:=lshift(tir); if n then goto 25;",
    25: "alu:=tir; if n then goto 27;",
    
    # JUMP / JZER / JNEG / LOCO
    26: "pc:=band(ir, amask); goto 0;", # JUMP
    27: "ac:=band(ir, amask); goto 0;", # LOCO
    
    # Decodificação 1xxx
    28: "tir:=lshift(ir + ir); if n then goto 40;",
    29: "tir:=lshift(tir); if n then goto 35;",
    30: "alu:=tir; if n then goto 33;",
    35: "alu:=tir; if n then goto 38;",
    
    # LODL (1000)
    31: "a:=ir + sp;",
    32: "mar:=a; rd; goto 7;",
    
    # STOL (1001)
    33: "a:=ir + sp;",
    34: "mar:=a; mbr:=ac; wr; goto 10;",
    
    # ADDL (1010)
    36: "a:=ir + sp;",
    37: "mar:=a; rd; goto 13;",
    
    # SUBL (1011)
    38: "a:=ir + sp;",
    39: "mar:=a; rd; goto 16;",
    
    # Decodificação Complexa (11xx)
    40: "tir:=lshift(tir); if n then goto 46;",
    41: "alu:=tir; if n then goto 44;",
    44: "alu:=ac; if z then goto 0;", # JNZE check
    45: "pc:=band(ir, amask); goto 0;", # JNZE jump
    
    46: "tir:=lshift(tir); if n then goto 50;",
    50: "tir:=lshift(tir); if n then goto 65;",
    51: "tir:=lshift(tir); if n then goto 59;",
    59: "alu:=tir; if n then goto 62;",
    
    # PUSH (1111 0100)
    60: "sp:=sp + (-1);",
    61: "mar:=sp; mbr:=ac; wr; goto 10;",
    
    # POP (1111 0110)
    62: "mar:=sp; sp:=sp + 1; rd;",
    63: "rd;",
    64: "ac:=mbr; goto 0;",
    
    # SWAP / RETN placeholder
    65: "tir:=lshift(tir); if n then goto 73;",
    70: "a:=ac;",
    71: "ac:=sp;",
    72: "sp:=a; goto 0;"
}

class MIC1:
    def __init__(self):
        self.control_store = CONTROL_STORE
        self.main_memory = Memory()
        self.alu = ALU()
        self.shifter = Shifter()
        self.amux = Amux()

        # Registradores
        self.registers = [Register(f"R{i}") for i in range(16)]
        
        # Aliases
        self.pc = self.registers[0]; self.pc.name = "PC"
        self.ac = self.registers[1]; self.ac.name = "AC"
        self.sp = self.registers[2]; self.sp.name = "SP"
        self.ir = self.registers[3]; self.ir.name = "IR"
        self.tir = self.registers[4]; self.tir.name = "TIR"
        self.zero = self.registers[5]; self.zero.name = "0"
        self.plus1 = self.registers[6]; self.plus1.name = "+1"
        self.minus1 = self.registers[7]; self.minus1.name = "-1"
        self.amask = self.registers[8]; self.amask.name = "AMASK"
        self.smask = self.registers[9]; self.smask.name = "SMASK"
        for i, name in enumerate("ABCDEF", 10):
            self.registers[i].name = name

        self.mar = Register("MAR")
        self.mbr = Register("MBR")
        self.mpc = Register("MPC")
        self.mir = 0

        self.latch_a = 0
        self.latch_b = 0
        
        self.reset()

    def reset(self):
        for i in [0, 1, 3, 4] + list(range(10, 16)):
            self.registers[i].write(0)
        
        self.sp.write(4096)
        self.zero.write(0)
        self.plus1.write(1)
        self.minus1.write(-1)
        self.amask.write(0x0FFF)
        self.smask.write(0x00FF)

        self.mar.write(0)
        self.mbr.write(0)
        self.mpc.write(0)
        self.mir = 0
        
        self.main_memory.clear()
        
        self.is_running = False
        self.stop_flag = False
        self.cycle_count = 0
        self.execution_start_time = 0
        self.micro_history = []
        self.breakpoint_pc = -1
        
        self.n_flag = False
        self.z_flag = False

    def _get_field(self, shift, mask):
        return (self.mir >> shift) & mask

    def step(self):
        if not self.is_running or self.stop_flag:
            return

        # 1. Busca MIR
        current_mpc = self.mpc.read()
        self.mir = self.control_store[current_mpc]
        
        # 2. Histórico formatado (Usa o dicionário ou o decodificador genérico)
        decoded_str = MICRO_MNEMONICS.get(current_mpc, self.decode_generic_microinstruction())
        
        # Formata com o número da linha: "0: mar:=pc; rd;"
        self.micro_history.insert(0, f"{current_mpc}: {decoded_str}")
        if len(self.micro_history) > 50: self.micro_history.pop()

        # --- Subciclo 1: Memoria ---
        self.main_memory.access(self.mbr)

        # --- Subciclo 2: Decodificação e Latches ---
        addr_a = self._get_field(8, 0xF)
        addr_b = self._get_field(12, 0xF)
        self.latch_a = self.registers[addr_a].read()
        self.latch_b = self.registers[addr_b].read()

        # --- Subciclo 3: ALU e Shifter ---
        amux_sig = self._get_field(31, 0x1)
        alu_sig = self._get_field(27, 0x3)
        sh_sig = self._get_field(25, 0x3)
        mar_load = self._get_field(23, 0x1)

        amux_out = self.amux.decide_output(amux_sig, self.latch_a, self.mbr.read())
        
        if mar_load == 1:
            self.mar.write(self.latch_b)

        alu_out, self.n_flag, self.z_flag = self.alu.execute(alu_sig, amux_out, self.latch_b)
        c_bus = self.shifter.execute(sh_sig, alu_out)

        # --- Subciclo 4: Writeback e Prox Endereço ---
        enc = self._get_field(20, 0x1)
        c_addr = self._get_field(16, 0xF)
        wr_sig = self._get_field(21, 0x1)
        rd_sig = self._get_field(22, 0x1)
        mbr_load = self._get_field(24, 0x1)

        if enc == 1:
            self.registers[c_addr].write(c_bus)
        
        if mbr_load == 1:
            self.mbr.write(c_bus)

        if rd_sig == 1:
            self.main_memory.enable_read(self.mar.read())
        if wr_sig == 1:
            self.main_memory.enable_write(self.mar.read())

        cond = self._get_field(29, 0x3)
        jump_addr = self._get_field(0, 0xFF)
        
        next_mpc_val = self.mpc.read() + 1
        
        take_jump = False
        if cond == 1 and self.n_flag: take_jump = True    # N
        elif cond == 2 and self.z_flag: take_jump = True  # Z
        elif cond == 3: take_jump = True                  # Always

        if take_jump:
            next_mpc_val = jump_addr
            
        self.mpc.write(next_mpc_val)
        self.cycle_count += 1

        # Breakpoint Check
        if self.pc.read() == self.breakpoint_pc and self.pc.read() != 0 and self.mpc.read() == 0:
            self.is_running = False
            self.stop_flag = True

    def decode_generic_microinstruction(self) -> str:
        """Fallback para quando não houver mnemônico definido"""
        bus_a = self.registers[self._get_field(8, 0xF)].name
        bus_b = self.registers[self._get_field(12, 0xF)].name
        bus_c = self.registers[self._get_field(16, 0xF)].name
        alu_op_code = self._get_field(27, 0x3)
        amux = self._get_field(31, 0x1)
        enc = self._get_field(20, 0x1)
        mem = ""
        if self._get_field(22, 0x1): mem = "RD"
        elif self._get_field(21, 0x1): mem = "WR"
        
        alu_map = {0: "ADD", 1: "AND", 2: "PASS_A", 3: "INV_A"}
        op = alu_map[alu_op_code]
        
        input_a = "MBR" if amux else bus_a
        action = f"{op}({input_a}, {bus_b})"
        if enc: action += f" -> {bus_c}"
        if mem: action += f" [{mem}]"
            
        return action

    def get_state(self) -> dict:
        exec_time = (time.time() - self.execution_start_time) if self.execution_start_time > 0 else 0
        
        view_program = self.main_memory.get_memory_view(0, 128)
        view_stack = self.main_memory.get_memory_view(4064, 32)

        return {
            "registers": {
                "PC": self.pc.read(), "AC": self.ac.read(), "SP": self.sp.read(),
                "IR": self.ir.read(), "TIR": self.tir.read(), 
                "MAR": self.mar.read(), "MBR": self.mbr.read()
            },
            "flags": {"N": self.n_flag, "Z": self.z_flag},
            "simulation": {
                "isRunning": self.is_running, "isStopped": self.stop_flag,
                "mpc": self.mpc.read(), "cycleCount": self.cycle_count,
                "executionTimeMs": int(exec_time * 1000),
            },
            "microHistory": self.micro_history,
            "memoryView": view_program + view_stack 
        }