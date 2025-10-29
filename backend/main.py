# backend/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .cpu import MIC1
from .assembler import assemble
import asyncio
import time

app = FastAPI(title="MIC-1 Simulator API")

simulator = MIC1()

class Code(BaseModel):
    source: str

class Control(BaseModel):
    value: int

@app.post("/assemble_and_load", summary="Montar e Carregar Programa")
def assemble_and_load(code: Code):
    """Monta o código assembly e, se bem-sucedido, carrega na memória."""
    simulator.reset()
    bytecode, error = assemble(code.source)
    if error:
        raise HTTPException(status_code=400, detail=error)
    
    for i, instruction in enumerate(bytecode):
        simulator.main_memory.write(i, instruction)
    
    return {"message": f"{len(bytecode)} palavras carregadas na memória.", "state": simulator.get_state()}

@app.get("/status", summary="Obter Estado Atual")
def get_status():
    return simulator.get_state()

@app.post("/run", summary="Iniciar Simulação")
async def run_simulation(control: Control):
    """Inicia a execução contínua com um delay entre os ciclos."""
    simulator.is_running = True
    simulator.stop_flag = False
    if simulator.cycle_count == 0:
        simulator.execution_start_time = time.time()

    delay = control.value / 1000.0 # Delay em segundos
    while simulator.is_running:
        simulator.step()
        await asyncio.sleep(delay)
    
    return {"message": "Simulation paused or stopped.", "state": simulator.get_state()}

@app.post("/step", summary="Executar Um Ciclo")
def execute_step():
    """Executa um único microciclo (passo-a-passo)."""
    simulator.is_running = True # Permite um único passo mesmo se pausado
    simulator.step()
    simulator.is_running = False
    return simulator.get_state()

@app.post("/pause", summary="Pausar Simulação")
def pause_simulation():
    simulator.is_running = False
    return {"message": "Simulation paused.", "state": simulator.get_state()}

@app.post("/reset", summary="Resetar Simulador")
def reset_simulation():
    """Limpa memória, registradores e pausa a simulação."""
    simulator.reset()
    return {"message": "Simulator reset.", "state": simulator.get_state()}

@app.post("/set_breakpoint", summary="Definir Breakpoint")
def set_breakpoint(control: Control):
    """Define um valor de PC para pausar a simulação automaticamente.""" 
    simulator.breakpoint_pc = control.value
    return {"message": f"Breakpoint set at PC={control.value}."}