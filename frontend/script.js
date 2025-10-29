document.addEventListener('DOMContentLoaded', () => {
    // URL base da nossa API Python
    const API_BASE_URL = 'http://127.0.0.1:8000';

    // --- Elementos da UI ---
    const assemblyInput = document.getElementById('assembly-input');
    const compiledOutput = document.getElementById('compiled-output');
    const montarBtn = document.getElementById('montar-btn');
    const gravarMpBtn = document.getElementById('gravar-mp-btn');
    
    const playBtn = document.getElementById('play-btn');
    const pauseBtn = document.getElementById('pause-btn');
    const resetBtn = document.getElementById('reset-btn');
    const nextStepBtn = document.getElementById('next-step-btn');
    
    const speedInput = document.getElementById('speed-input');
    const breakpointInput = document.getElementById('breakpoint-input');
    const applyBreakpointBtn = document.getElementById('apply-breakpoint-btn');

    let simInterval = null;

    // --- FUNÇÃO PRINCIPAL DE ATUALIZAÇÃO DA UI ---
    function updateUI(state) {
        if (!state) return;

        const registersBody = document.getElementById('registers-table-body');
        registersBody.innerHTML = '';
        for (const [reg, val] of Object.entries(state.registers)) {
            registersBody.innerHTML += `<tr><td>${reg}</td><td>${val}</td></tr>`;
        }
        
        const memoryBody = document.getElementById('memory-table-body');
        memoryBody.innerHTML = '';
        if (state.memoryView) {
            state.memoryView.forEach(mem => {
                memoryBody.innerHTML += `
                    <tr>
                        <td>${mem.address}</td>
                        <td>${mem.hex}</td>
                        <td>${mem.decimal}</td>
                        <td>${mem.binary}</td>
                    </tr>
                `;
            });
        }
        
        document.getElementById('cycle-count').textContent = state.simulation.cycleCount;
        document.getElementById('exec-time').textContent = state.simulation.executionTimeMs;
        document.getElementById('micro-history-box').innerHTML = state.microHistory.join('<br>');
    }

    // --- FUNÇÕES DE CONTROLE DA API ---

    // 1. Montar o código
    montarBtn.addEventListener('click', async () => {
        const sourceCode = assemblyInput.value;
        try {
            const response = await fetch(`${API_BASE_URL}/assemble`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source: sourceCode })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail);
            
            // Exibe o bytecode hexadecimal na caixa de texto
            compiledOutput.value = data.bytecode.join('\n');
            
        } catch (error) {
            alert('Erro ao montar o programa: ' + error.message);
            compiledOutput.value = '';
        }
    });

    // 2. Gravar o código compilado na memória
    gravarMpBtn.addEventListener('click', async () => {
        const hexBytecode = compiledOutput.value;
        if (!hexBytecode) {
            alert("Primeiro, monte um programa usando o botão 'Montar'.");
            return;
        }

        // Converte o texto hexadecimal de volta para uma lista de números inteiros
        const bytecodeInts = hexBytecode.split('\n').map(hex => parseInt(hex, 16));

        try {
            const response = await fetch(`${API_BASE_URL}/load`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bytecode: bytecodeInts })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail);
            
            updateUI(data.state);
            alert('Programa gravado na memória principal!');
        } catch (error) {
            alert('Erro ao gravar na memória: ' + error.message);
        }
    });

    // Função de passo a passo
    async function executeStep() {
        try {
            const response = await fetch(`${API_BASE_URL}/step`, { method: 'POST' });
            const state = await response.json();
            updateUI(state);
            if (!state.simulation.isRunning && simInterval) {
                clearInterval(simInterval);
                simInterval = null;
            }
        } catch (error) {
            console.error('Erro ao executar o passo:', error);
            clearInterval(simInterval);
        }
    }
    nextStepBtn.addEventListener('click', executeStep);

    // Botões Play/Pause/Reset... (sem alterações)
    playBtn.addEventListener('click', () => {
        if (simInterval) return;
        const speed = parseInt(speedInput.value) || 200;
        simInterval = setInterval(executeStep, speed);
    });
    pauseBtn.addEventListener('click', () => {
        if (simInterval) {
            clearInterval(simInterval);
            simInterval = null;
        }
    });
    resetBtn.addEventListener('click', async () => {
        if (simInterval) clearInterval(simInterval);
        simInterval = null;
        const response = await fetch(`${API_BASE_URL}/reset`, { method: 'POST' });
        const data = await response.json();
        updateUI(data.state);
        compiledOutput.value = ''; // Limpa a caixa de compilado
    });
    applyBreakpointBtn.addEventListener('click', async () => {
        const pcValue = parseInt(breakpointInput.value);
        if (isNaN(pcValue)) { // Permite breakpoint em 0
            alert("Por favor, insira um valor de PC válido.");
            return;
        }
        await fetch(`${API_BASE_URL}/set_breakpoint`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: pcValue })
        });
        alert(`Breakpoint aplicado em PC = ${pcValue}`);
    });

    // Carregar estado inicial
    async function getInitialState() {
        try {
            const response = await fetch(`${API_BASE_URL}/status`);
            const state = await response.json();
            updateUI(state);
        } catch (error) {
            console.error("Não foi possível conectar ao backend.", error);
            alert("Erro de conexão: Verifique se o servidor backend está rodando.");
        }
    }
    getInitialState();
});