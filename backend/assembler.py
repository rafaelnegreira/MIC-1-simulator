import re

OPCODE_MAP = {
    "LODD": 0b0000, "STOD": 0b0001, "ADDD": 0b0010, "SUBD": 0b0011,
    "JPOS": 0b0100, "JZER": 0b0101, "JUMP": 0b0110, "LOCO": 0b0111,
    "LODL": 0b1000, "STOL": 0b1001, "ADDL": 0b1010, "SUBL": 0b1011,
    "JNEG": 0b1100, "JNZE": 0b1101, "CALL": 0b1110
}

FULL_OPCODE_MAP = {
    "PSHI": 0xF000, "POPI": 0xF200, "PUSH": 0xF400, "POP": 0xF600,
    "RETN": 0xF800, "SWAP": 0xFA00, "INSP": 0xFC00, "DESP": 0xFE00
}

def assemble(source_code: str) -> tuple[list[int] | None, str | None]:
    lines = source_code.strip().upper().splitlines()
    labels = {}
    variables = {}
    instructions = []
    
    # 1. Primeira Passagem: Contar endereços e achar labels
    code_address_counter = 0
    for i, line in enumerate(lines):
        line = line.split('/')[0].strip()
        if not line: continue
        
        match = re.match(r'^([A-Z0-9_]+):\s*(.*)', line)
        if match:
            label, rest_of_line = match.groups()
            labels[label] = code_address_counter
            line = rest_of_line.strip()
        
        if not line: continue
        
        parts = line.split()
        mnemonic = parts[0]
        operand = parts[1] if len(parts) > 1 else None
        
        instructions.append({
            "address": code_address_counter,
            "mnemonic": mnemonic,
            "operand": operand,
            "line": i + 1
        })
        code_address_counter += 1

    # CORREÇÃO: Variáveis começam imediatamente após o código
    var_address_counter = code_address_counter 

    # 2. Alocar variáveis
    for instr in instructions:
        mnemonic = instr["mnemonic"]
        operand = instr["operand"]
        
        if mnemonic in ["LODD", "STOD", "ADDD", "SUBD"] and operand:
            if operand not in labels and operand not in variables:
                try:
                    int(operand)
                except ValueError:
                    variables[operand] = var_address_counter
                    var_address_counter += 1

    # 3. Segunda Passagem: Gerar Bytecode
    bytecode = [0] * code_address_counter
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
                        return None, f"Erro na linha {instr['line']}: '{operand}' não encontrado."
            
            machine_word = (opcode << 12) | (operand_val & 0xFFF)
        
        elif mnemonic in FULL_OPCODE_MAP:
            machine_word = FULL_OPCODE_MAP[mnemonic]
            if mnemonic in ["INSP", "DESP"] and operand:
                machine_word |= (int(operand) & 0xFF)
        else:
            return None, f"Erro na linha {instr['line']}: Mnemônico '{mnemonic}' desconhecido."

        bytecode[address] = machine_word

    return bytecode, None