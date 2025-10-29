# backend/components.py
"""
Define os componentes de hardware básicos do simulador MIC-1,
baseado na arquitetura dos PDFs fornecidos.
"""
import ctypes

class Register:
    """Simula um registrador genérico de 16 bits."""
    def __init__(self, name: str):
        self.name = name
        # Usa ctypes para simular o comportamento de inteiros com sinal de 16 bits
        self.value = ctypes.c_int16(0)

    def write(self, data: int):
        self.value.value = data

    def read(self) -> int:
        return self.value.value

class ALU:
    """Simula a Unidade Lógica e Aritmética (ULA)."""
    def execute(self, op: str, a_bus_val: int, b_bus_val: int) -> tuple[int, bool, bool]:
        """
        Executa uma operação da ULA.
        Retorna (resultado, flag_N, flag_Z).
        """
        result = 0
        if op == "ADD":
            result = a_bus_val + b_bus_val
        elif op == "BAND":
            result = a_bus_val & b_bus_val
        elif op == "INV":
            result = ~a_bus_val
        elif op == "PASS_A":
            result = a_bus_val
        elif op == "PASS_B":
            result = b_bus_val
        elif op == "INC_A":
            result = a_bus_val + 1
        else: # Default pass-through
            result = a_bus_val

        # Simula o comportamento de 16 bits
        result_16bit = ctypes.c_int16(result).value

        # Define as flags N (negativo) e Z (zero)
        n_flag = result_16bit < 0
        z_flag = result_16bit == 0

        return result_16bit, n_flag, z_flag

class Shifter:
    """Simula o Shifter."""
    def execute(self, op: str, data: int) -> int:
        if op == "SLL1": # Shift Left Logical 1
            # Multiplicar por 2 é equivalente a um shift left
            return (data << 1)
        return data

class Memory:
    """Simula a memória principal."""
    def __init__(self, size=4096): # Memória para endereços de 12 bits
        self.size = size
        self.data = [ctypes.c_int16(0) for _ in range(size)]

    def write(self, address: int, value: int):
        if 0 <= address < self.size:
            self.data[address].value = value

    def read(self, address: int) -> int:
        if 0 <= address < self.size:
            return self.data[address].value
        return 0

    def get_memory_view(self, start_addr: int, count: int) -> list[dict]:
        """Retorna uma porção da memória para visualização."""
        view = []
        end_addr = min(start_addr + count, self.size)
        for addr in range(start_addr, end_addr):
            val = self.read(addr)
            view.append({
                "address": addr,
                "hex": f"{val & 0xFFFF:04X}",
                "decimal": val,
                "binary": f"{val & 0xFFFF:016b}"
            })
        return view
    
    # Dentro da classe Memory em backend/components.py

    def clear(self):
        """Reseta todos os valores da memória para zero."""
        for i in range(self.size):
            self.data[i].value = 0