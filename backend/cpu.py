# backend/cpu.py
from .components import Register, ALU, Shifter, Memory
from .microcode import MICROCODE
import time
import ctypes

class MIC1:
    """Simula a CPU MIC-1 completa, baseada na arquitetura dos PDFs."""

    def __init__(self):
        self.control_store = MICROCODE
        self.main_memory = Memory()
        self.alu = ALU()
        self.shifter = Shifter()

        # Registradores da arquitetura [cite: 99]
        self.pc = Register("PC")    # Program Counter [cite: 102]
        self.ac = Register("AC")    # Accumulator [cite: 103]
        self.sp = Register("SP")    # Stack Pointer [cite: 104]
        self.ir = Register("IR")    # Instruction Register [cite: 105]
        self.tir = Register("TIR")  # Temporary Instruction Register [cite: 106]
        self.mar = Register("MAR")  # Memory Address Register [cite: 124]
        self.mbr = Register("MBR")  # Memory Buffer Register [cite: 128]
        self.a_latch = Register("A_LATCH") # Latch de entrada A para a ALU [cite: 120]
        
        # Constantes
        self.amask = 0b0000111111111111 # 4095
        
        self.all_registers = {
            "PC": self.pc, "AC": self.ac, "SP": self.sp, "IR": self.ir,
            "TIR": self.tir, "MAR": self.mar, "MBR": self.mbr
        }
        self.reset()

    def reset(self):
        """Limpa a memória, os registradores e pausa a simulação."""
        # Limpa todos os registradores
        for reg in self.all_registers.values():
            reg.write(0)

        # Limpa a memória principal
        self.main_memory.clear()

        # Reseta o estado da simulação e contadores
        self.mpc = 0
        self.n_flag, self.z_flag = False, True
        self.is_running, self.stop_flag = False, False
        self.cycle_count = 0
        self.execution_start_time = 0
        self.micro_history = []
        self.breakpoint_pc = -1

    def _get_bus_value(self, source_name: str) -> int:
        """Obtém o valor de um registrador para colocar em um barramento."""
        if source_name in self.all_registers:
            return self.all_registers[source_name].read()
        if source_name == "A_LATCH":
            return self.a_latch.read()
        return 0

    # Em backend/cpu.py
    def step(self):
        """Executa um único ciclo de clock (uma microinstrução)."""
        if not self.is_running or self.stop_flag:
            return

        # 1. Pega a microinstrução atual e atualiza o histórico
        micro_instr = self.control_store.get(self.mpc, {})
        self.micro_history.insert(0, f"{self.mpc}: {micro_instr}")
        if len(self.micro_history) > 50: self.micro_history.pop()

        # 2. Simula os barramentos, ULA e Shifter
        a_bus_val = self._get_bus_value(micro_instr.get("a_bus", "AC"))
        b_bus_val = self._get_bus_value(micro_instr.get("b_bus", "MBR"))
        
        value_to_write = 0
        if "shifter_op" in micro_instr:
            shifter_result = self.shifter.execute(micro_instr["shifter_op"], a_bus_val)
            result_16bit = ctypes.c_int16(shifter_result).value
            self.n_flag = result_16bit < 0
            self.z_flag = result_16bit == 0
            value_to_write = shifter_result
        else:
            alu_result, self.n_flag, self.z_flag = self.alu.execute(
                micro_instr.get("alu_op"), a_bus_val, b_bus_val
            )
            value_to_write = alu_result

        # 3. Escreve no barramento C
        c_bus_dest = micro_instr.get("c_bus")
        if c_bus_dest:
            # Aplica a máscara se a intenção é extrair um operando de 12 bits do IR.
            # Isso acontece em todas as instruções de endereçamento direto, JUMPs e LOCO.
            if self.mpc in [6, 9, 12, 15, 22, 26, 27]:
                value_to_write &= self.amask
        
            if c_bus_dest in self.all_registers:
                self.all_registers[c_bus_dest].write(value_to_write)
            elif c_bus_dest == "A_LATCH":
                self.a_latch.write(value_to_write)

        # 4. Operações de Memória
        if micro_instr.get("mem") == "RD":
            self.mbr.write(self.main_memory.read(self.mar.read()))
        elif micro_instr.get("mem") == "WR":
            self.main_memory.write(self.mar.read(), self.mbr.read())

        # 5. Calcula o próximo MPC
        jump_conds = micro_instr.get("cond_jump", {})
        if "if_n" in jump_conds and self.n_flag:
            self.mpc = jump_conds["if_n"]
        elif "if_z" in jump_conds and self.z_flag:
            self.mpc = jump_conds["if_z"]
        else:
            self.mpc = micro_instr.get("next_addr", 0)
        
        self.cycle_count += 1
        if self.pc.read() == self.breakpoint_pc:
            self.is_running = False

    def get_state(self) -> dict:
        """Retorna o estado completo atual do simulador."""
        exec_time = (time.time() - self.execution_start_time) if self.execution_start_time > 0 else 0
        return {
            "registers": {name: reg.read() for name, reg in self.all_registers.items()},
            "flags": {"N": self.n_flag, "Z": self.z_flag},
            "simulation": {
                "isRunning": self.is_running,
                "isStopped": self.stop_flag,
                "mpc": self.mpc,
                "cycleCount": self.cycle_count,
                "executionTimeMs": int(exec_time * 1000),
            },
            "microHistory": self.micro_history,
            "memoryView": self.main_memory.get_memory_view(0, 64) # Exibe os primeiros 64 endereços
        }
    
    # ... outros métodos como run, pause, stop, etc.