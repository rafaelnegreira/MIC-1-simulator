# backend/main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .cpu import MIC1
from .assembler import assemble
import asyncio
import time

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MIC-1 Simulator API")

origins = [
    "http://localhost",
    "http://localhost:8080",
    "null",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)

simulator = MIC1()

# --- Modelos de Dados para a API ---
class AssemblyPayload(BaseModel):
    source: str

class BytecodePayload(BaseModel):
    bytecode: list[int]

class ControlPayload(BaseModel):
    value: int

@app.post("/assemble", summary="Montar Código Assembly")
def assemble_code(payload: AssemblyPayload):
    bytecode, error = assemble(payload.source)
    if error:
        raise HTTPException(status_code=400, detail=error)
    
    binary_bytecode = [f"{val & 0xFFFF:016b}" for val in bytecode]
    
    return {"bytecode": binary_bytecode}

@app.post("/load", summary="Carregar Bytecode na Memória")
def load_memory(payload: BytecodePayload):
    simulator.reset()
    for i, instruction in enumerate(payload.bytecode):
        simulator.main_memory.direct_write(i, instruction)
    return {"message": f"{len(payload.bytecode)} palavras carregadas na memória.", "state": simulator.get_state()}

@app.get("/status", summary="Obter Estado Atual")
def get_status():
    return simulator.get_state()

@app.post("/run", summary="Iniciar Simulação")
async def run_simulation(control: ControlPayload):
    simulator.is_running = True
    simulator.stop_flag = False
    if simulator.cycle_count == 0:
        simulator.execution_start_time = time.time()
    delay = control.value / 1000.0
    while simulator.is_running:
        simulator.step()
        await asyncio.sleep(delay)
    return {"message": "Simulação pausada ou parada.", "state": simulator.get_state()}

@app.post("/step", summary="Executar Um Ciclo")
def execute_step():
    # Se o frontend pediu para andar, forçamos o estado de execução
    simulator.is_running = True
    
    # CORREÇÃO: Destravamos o flag de parada para permitir sair do Breakpoint
    simulator.stop_flag = False 
    
    simulator.step()
    return simulator.get_state()
        
    simulator.step()
    return simulator.get_state()

@app.post("/pause", summary="Pausar Simulação")
def pause_simulation():
    simulator.is_running = False
    return {"message": "Simulação pausada.", "state": simulator.get_state()}

@app.post("/reset", summary="Resetar Simulador")
def reset_simulation():
    simulator.reset()
    return {"message": "Simulador resetado.", "state": simulator.get_state()}

@app.post("/set_breakpoint", summary="Definir Breakpoint")
def set_breakpoint(control: ControlPayload):
    simulator.breakpoint_pc = control.value
    return {"message": f"Breakpoint set at PC={control.value}."}