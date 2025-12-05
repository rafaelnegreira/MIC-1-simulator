# backend/components.py
import ctypes

class Register:
    def __init__(self, name: str, initial_value: int = 0):
        self.name = name
        self.value = ctypes.c_int16(initial_value)

    def write(self, data: int):
        self.value.value = data

    def read(self) -> int:
        return self.value.value

class Amux:
    def decide_output(self, control_signal: int, latch_a: int, mbr: int) -> int:
        # 1 = MBR, 0 = Latch A
        if control_signal == 1:
            return mbr
        return latch_a

class ALU:
    # Códigos baseados estritamente em ALU.java
    ADD = 0b00
    AND = 0b01
    PASS_A = 0b10
    INV_A = 0b11

    def execute(self, op: int, input_a: int, input_b: int) -> tuple[int, bool, bool]:
        result = 0
        # Força inputs para int nativo do python para cálculo
        val_a = input_a
        val_b = input_b

        if op == self.ADD:
            result = val_a + val_b
        elif op == self.AND:
            result = val_a & val_b
        elif op == self.PASS_A:
            result = val_a
        elif op == self.INV_A:
            result = ~val_a
        
        # Converte para 16 bits signed
        res_c = ctypes.c_int16(result)
        
        # Flags baseadas no resultado truncado
        z_flag = (res_c.value == 0)
        n_flag = (res_c.value < 0)
        
        return res_c.value, n_flag, z_flag

class Shifter:
    # Códigos baseados em Shifter.java (atenção aos códigos do PDF/Java)
    # No Java: 00=No, 01=Right, 10=Left. 
    # Porém, no PDF às vezes varia. Vamos usar a lógica do Java fornecido.
    NO_SHIFT = 0b00
    RIGHT_SHIFT = 0b01
    LEFT_SHIFT = 0b10

    def execute(self, op: int, data: int) -> int:
        # Trata como unsigned 16 bits para shifts lógicos se necessário, 
        # mas Java faz arithmetic shift right (>>).
        val = ctypes.c_int16(data).value
        
        result = val
        if op == self.RIGHT_SHIFT:
            result = val >> 1 # Arithmetic shift (preserva sinal)
        elif op == self.LEFT_SHIFT:
            result = val << 1
            
        return ctypes.c_int16(result).value

class Memory:
    def __init__(self, size=4096):
        self.size = size
        self.data = [ctypes.c_int16(0) for _ in range(size)]
        
        # Simulação de latches de memória (como no Java)
        self.read_enable = False
        self.write_enable = False
        self.address_latch = 0

    def clear(self):
        for i in range(self.size):
            self.data[i].value = 0
        self.read_enable = False
        self.write_enable = False

    def enable_read(self, address: int):
        self.address_latch = address & 0x0FFF
        self.read_enable = True

    def enable_write(self, address: int):
        self.address_latch = address & 0x0FFF
        self.write_enable = True

    def access(self, mbr_register: Register):
        """
        Executado no início do ciclo (leitura) ou fim (escrita).
        Retorna True se houve acesso.
        """
        if self.read_enable:
            val = self.data[self.address_latch].value
            mbr_register.write(val)
            self.read_enable = False
            return True
        
        if self.write_enable:
            val = mbr_register.read()
            self.data[self.address_latch].value = val
            self.write_enable = False
            return True
            
        return False

    # Métodos diretos para carga inicial (Load Program)
    def direct_write(self, address: int, value: int):
        masked_addr = address & 0x0FFF
        if 0 <= masked_addr < self.size:
            self.data[masked_addr].value = value

    def get_memory_view(self, start_addr: int, count: int) -> list[dict]:
        view = []
        end_addr = min(start_addr + count, self.size)
        for addr in range(start_addr, end_addr):
            val = self.data[addr].value
            view.append({
                "address": addr,
                "hex": f"{val & 0xFFFF:04X}",
                "decimal": val,
                "binary": f"{val & 0xFFFF:016b}"
            })
        return view