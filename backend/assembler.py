# backend/assembler.py
import re

# Mapa de mnemônicos para seus opcodes de 4 bits. [cite: 191]
OPCODE_MAP = {
    "LODD": 0b0000, "STOD": 0b0001, "ADDD": 0b0010, "SUBD": 0b0011,
    "JPOS": 0b0100, "JZER": 0b0101, "JUMP": 0b0110, "LOCO": 0b0111,
    "LODL": 0b1000, "STOL": 0b1001, "ADDL": 0b1010, "SUBL": 0b1011,
    "JNEG": 0b1100, "JNZE": 0b1101, "CALL": 0b1110
    # Instruções de 16 bits são casos especiais
}

# Instruções de 16 bits
FULL_OPCODE_MAP = {
    "PSHI": 0xF000, "POPI": 0xF200, "PUSH": 0xF400, "POP": 0xF600,
    "RETN": 0xF800, "SWAP": 0xFA00, "INSP": 0xFC00, "DESP": 0xFE00
}

def assemble(source_code: str) -> tuple[list[int] | None, str | None]:
    """
    Monta o código assembly MIC-1 para bytecode.
    Retorna uma tupla de (bytecode_list, error_message).
    """
    lines = source_code.strip().upper().splitlines()
    labels = {}
    variables = {}
    var_address_counter = 4000 # Variáveis são alocadas no final da memória
    instructions = []

    # 1º Passo: Processar linhas, encontrar labels e variáveis
    current_address = 0
    for i, line in enumerate(lines):
        line = line.split('/')[0].strip() # Remove comentários [cite: 70]
        if not line:
            continue
        
        match = re.match(r'^([A-Z0-9_]+):\s*(.*)', line)
        if match:
            label, rest_of_line = match.groups()
            labels[label] = current_address
            line = rest_of_line.strip()
        
        if not line: continue
        
        parts = line.split()
        mnemonic = parts[0]
        operand = parts[1] if len(parts) > 1 else None

        instructions.append({"address": current_address, "mnemonic": mnemonic, "operand": operand, "line": i + 1})
        current_address += 1

        # Alocar variáveis dinamicamente
        if mnemonic in ["LODD", "STOD", "ADDD", "SUBD"] and operand not in variables:
            variables[operand] = var_address_counter
            var_address_counter += 1
            
    # 2º Passo: Gerar bytecode
    bytecode = [0] * current_address
    for instr in instructions:
        address = instr["address"]
        mnemonic = instr["mnemonic"]
        operand = instr["operand"]
        
        machine_word = 0
        if mnemonic in OPCODE_MAP:
            opcode = OPCODE_MAP[mnemonic]
            operand_val = 0
            if operand:
                if operand in labels:
                    operand_val = labels[operand]
                elif operand in variables:
                    operand_val = variables[operand]
                else:
                    try:
                        operand_val = int(operand)
                    except ValueError:
                        return None, f"Erro na linha {instr['line']}: Label ou variável '{operand}' não encontrado."
            
            machine_word = (opcode << 12) | (operand_val & 0xFFF)
        
        elif mnemonic in FULL_OPCODE_MAP:
            machine_word = FULL_OPCODE_MAP[mnemonic]
            # INSP e DESP podem ter operandos
            if mnemonic in ["INSP", "DESP"] and operand:
                machine_word |= (int(operand) & 0xFF)
        else:
            return None, f"Erro na linha {instr['line']}: Mnemônico '{mnemonic}' desconhecido."

        bytecode[address] = machine_word

    return bytecode, None