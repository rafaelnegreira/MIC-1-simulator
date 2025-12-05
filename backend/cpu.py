# backend/cpu.py
import time
import ctypes
from .components import Register, ALU, Shifter, Memory, Amux
from .microcode import CONTROL_STORE

class MIC1:
    def __init__(self):
        self.control_store = CONTROL_STORE
        self.main_memory = Memory()
        self.alu = ALU()
        self.shifter = Shifter()
        self.amux = Amux()

        # Registradores (Indices fixos para acesso via Barramento)
        self.registers = [Register(f"R{i}") for i in range(16)]
        
        # Aliases para facilitar leitura no código
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
        # Registradores A-F (10-15)
        for i, name in enumerate("ABCDEF", 10):
            self.registers[i].name = name

        # Registradores Especiais (fora do banco geral)
        self.mar = Register("MAR")
        self.mbr = Register("MBR")
        self.mpc = Register("MPC") # Micro Program Counter
        self.mir = 0 # Micro Instruction Register (int 32 bits)

        # Latches internos
        self.latch_a = 0
        self.latch_b = 0
        
        self.reset()

    def reset(self):
        # Zera registradores (exceto constantes)
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
        
        # Flags de controle de simulação
        self.is_running = False
        self.stop_flag = False
        self.cycle_count = 0
        self.execution_start_time = 0
        self.micro_history = []
        self.breakpoint_pc = -1
        
        # Flags da ALU
        self.n_flag = False
        self.z_flag = False

    def _get_field(self, shift, mask):
        return (self.mir >> shift) & mask

    def step(self):
        """Executa um ciclo completo de clock (4 subciclos)"""
        if not self.is_running or self.stop_flag:
            return

        # Busca Microinstrução
        self.mir = self.control_store[self.mpc.read()]
        
        # Histórico para o Frontend (Decodifica o binário para texto)
        decoded_str = self.decode_current_microinstruction()
        self.micro_history.insert(0, f"{self.mpc.read()}: {decoded_str}")
        if len(self.micro_history) > 50: self.micro_history.pop()

        # --- Subciclo 1: Memoria ---
        # Verifica se houve pedido de leitura/escrita no ciclo ANTERIOR
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

        # Amux seleciona entre Latch A e MBR
        amux_out = self.amux.decide_output(amux_sig, self.latch_a, self.mbr.read())
        
        # Carga do MAR (ocorre na borda de subida do sub3)
        if mar_load == 1:
            self.mar.write(self.latch_b)

        # ALU Execute
        alu_out, self.n_flag, self.z_flag = self.alu.execute(alu_sig, amux_out, self.latch_b)
        
        # Shifter Execute
        c_bus = self.shifter.execute(sh_sig, alu_out)

        # --- Subciclo 4: Writeback e Prox Endereço ---
        enc = self._get_field(20, 0x1)
        c_addr = self._get_field(16, 0xF)
        wr_sig = self._get_field(21, 0x1)
        rd_sig = self._get_field(22, 0x1)
        mbr_load = self._get_field(24, 0x1)

        # Escrita no Banco de Registradores
        if enc == 1:
            self.registers[c_addr].write(c_bus)
        
        # Escrita no MBR (pelo barramento C)
        if mbr_load == 1:
            self.mbr.write(c_bus)

        # Sinais de Memória (para o PRÓXIMO ciclo)
        if rd_sig == 1:
            self.main_memory.enable_read(self.mar.read())
        if wr_sig == 1:
            self.main_memory.enable_write(self.mar.read())

        # Cálculo do Próximo MPC
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

        if self.pc.read() == self.breakpoint_pc and self.pc.read() != 0 and self.mpc.read() == 0:
            self.is_running = False
            self.stop_flag = True

    def decode_current_microinstruction(self) -> str:
        """Gera string descritiva para o frontend baseada nos bits do MIR atual"""
        # Extrai campos
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
        
        # Monta string estilo "ADD(AC, PC) -> AC"
        input_a = "MBR" if amux else bus_a
        action = f"{op}({input_a}, {bus_b})"
        
        if enc:
            action += f" -> {bus_c}"
            
        if mem:
            action += f" [{mem}]"
            
        return action

    def get_state(self) -> dict:
        exec_time = (time.time() - self.execution_start_time) if self.execution_start_time > 0 else 0
        
        # --- MUDANÇA AQUI: VISÃO INTELIGENTE ---
        # Pega as primeiras 128 posições (Código e Variáveis)
        view_program = self.main_memory.get_memory_view(0, 128)
        
        # Pega as últimas 32 posições (Pilha/Stack - endereços 4064 a 4096)
        # O Stack Pointer começa em 4096 e desce.
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
            
            # Combina as duas visões na lista enviada ao front
            "memoryView": view_program + view_stack 
        }