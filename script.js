// static/script.js

// Seleciona todos os elementos no início para performance
const pixStatusEl = document.getElementById('pix-status');
const updatedAtEl = document.getElementById('updated-at');

const historyBtn = document.getElementById('historyBtn');
const historyLogContainer = document.getElementById('historyLogContainer');
const historyLogList = document.getElementById('historyLogList');

// CORREÇÃO: Seleciona o span do texto
const historyBtnText = document.getElementById('history-btn-text');

let historyVisible = false;

/**
 * Helper para aplicar o status (texto e classe) em um elemento.
 */
function setStatus(element, statusText) {
    const status = statusText ? statusText.toLowerCase() : 'desconhecido';
    element.innerText = statusText || 'Desconhecido';
    element.dataset.status = status; // Usa data-status para o CSS
}

/**
 * Função principal para buscar e atualizar a UI.
 */
async function atualizarStatus() {
    try {
        const response = await fetch('/status');
        if (!response.ok) throw new Error('Falha na rede');
        
        const data = await response.json();
        
        // 1. Atualiza Status Principal
        setStatus(pixStatusEl, data.PIX);
        
        // 2. Atualiza Timestamp
        updatedAtEl.innerText = data.updated_at 
            ? new Date(data.updated_at).toLocaleString() 
            : "-";

    } catch (error) {
        // Modo de falha caso o *nosso* servidor caia
        setStatus(pixStatusEl, "Servidor Offline");
        updatedAtEl.innerText = "-";
        console.error("Erro ao atualizar status:", error);
    }
}

/**
 * Gerencia a visibilidade do histórico.
 */
async function toggleHistory() {
    historyVisible = !historyVisible;
    
    if (historyVisible) {
        historyLogContainer.style.display = 'block';
        
        // CORREÇÃO: Atualiza apenas o innerText do span
        historyBtnText.innerText = 'Esconder Histórico';
        
        historyBtn.setAttribute('aria-expanded', 'true');
        await carregarHistorico();
    } else {
        historyLogContainer.style.display = 'none';
        
        // CORREÇÃO: Atualiza apenas o innerText do span
        historyBtnText.innerText = 'Ver Histórico';
        
        historyBtn.setAttribute('aria-expanded', 'false');
    }
}

/**
 * Busca e renderiza o histórico de falhas.
 */
async function carregarHistorico() {
    historyLogList.innerHTML = '<li>Carregando...</li>';
    try {
        const response = await fetch('/history');
        if (!response.ok) throw new Error('Falha na rede');

        const logEntries = await response.json();
        
        historyLogList.innerHTML = ''; // Limpa o "Carregando"
        
        if (logEntries.length === 0) {
            historyLogList.innerHTML = '<li>Nenhum evento de falha registrado.</li>';
            return;
        }
        
        // Inverte para mostrar o mais recente primeiro
        logEntries.reverse().forEach(item => {
            const li = document.createElement('li');
            const dataFormatada = new Date(item.timestamp).toLocaleString();
            li.innerText = `[${dataFormatada}] - ${item.service} reportou: ${item.status}`;
            historyLogList.appendChild(li);
        });
        
    } catch (error) {
        historyLogList.innerHTML = '<li>Erro ao carregar histórico.</li>';
        console.error("Erro ao carregar histórico:", error);
    }
}

// -------- Inicialização --------

// Adiciona o listener ao botão
historyBtn.addEventListener('click', toggleHistory);

// Chama a função pela primeira vez
atualizarStatus();

// Configura o "refresh" automático
setInterval(atualizarStatus, 5000); // 5 segundos