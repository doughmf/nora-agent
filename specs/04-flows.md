# SPEC-04: Flows — Fluxos de Conversa e Decisão

**Versão:** 1.0  
**Status:** Aprovado

---

## 1. FLUXO PRINCIPAL (Master Flow)

```
[Mensagem recebida via WhatsApp]
           ↓
    [Verificar residente]
    ┌──── Conhecido ────┐
    │                   │
    ↓                   ↓
[Carregar          [Cadastrar novo
 perfil +           residente +
 histórico]         onboarding]
           ↓
    [Classificar intenção]
           ↓
    ┌──────┴──────┐
    │             │
  [RAG]     [Tool call]
    │             │
    └──────┬──────┘
           ↓
    [Gerar resposta]
           ↓
    [Salvar no histórico]
           ↓
    [Enviar via WhatsApp]
```

---

## 2. FLUXO: ABERTURA DE CHAMADO DE MANUTENÇÃO

```
Morador: "A lâmpada do corredor 3 está queimada"
           ↓
[Syndra confirma entendimento]
"Entendido! Vou registrar um chamado de manutenção. 
Me diga: isso está afetando a segurança agora?"

           ↓ Não / Sim
    ┌──────┴──────┐
 [P3 - Normal]  [P1 - Urgente]
 Prazo: 72h     Prazo: 2h
           ↓
[Gerar protocolo: MNT-2025-XXXX]
           ↓
[Notificar zelador via WhatsApp]
           ↓
[Resposta ao morador]:
"✅ Chamado aberto!
*Protocolo:* MNT-2025-0047
*Tipo:* Elétrica — Iluminação
*Local:* Corredor 3
*Prazo:* Até 72h
*Status:* Aguardando zelador

Você receberá uma atualização quando o reparo for concluído."
```

---

## 3. FLUXO: RESERVA DE ESPAÇO

```
Morador: "Quero reservar o salão para sábado"
           ↓
[Verificar data e disponibilidade]
           ↓
    ┌─── Disponível? ───┐
    │ Sim               │ Não
    ↓                   ↓
[Solicitar detalhes] [Oferecer alternativas]
- Período?           "Sábado está ocupado.
- Nº de convidados?  Posso verificar sexta
                      ou domingo para você?"
    ↓
[Exibir resumo + valor]
"📋 *Pré-reserva:*
Espaço: Salão de Festas
Data: 15/03/2025 (sábado)
Período: Noite (18h–23h)
Valor: R$ 200,00

Para confirmar, realize o Pix:
Chave: XX.XXX.XXX/0001-XX
Envie o comprovante aqui."
    ↓
[Morador envia comprovante]
    ↓
[Status → confirmado]
    ↓
[Confirmação + regras do espaço]
```

---

## 4. FLUXO: SITUAÇÃO DE EMERGÊNCIA

```
Morador: "Tem água vazando pelo teto do meu apartamento!"
           ↓
[Detectar palavras-chave de emergência]
           ↓
[Resposta imediata — Modo Urgência]:
"🚨 *SITUAÇÃO DE URGÊNCIA DETECTADA*

Estou notificando o zelador agora!

Enquanto isso:
• Desligue o disjuntor se houver risco elétrico
• Afaste móveis e objetos eletrônicos
• Se o vazamento vier de outro apartamento, 
  toque na porta do vizinho acima

*Zelador:* (XX) 9XXXX-XXXX
*Portaria:* (XX) 9XXXX-XXXX"
           ↓
[Notificar síndico + zelador automaticamente]
           ↓
[Abrir chamado P1 automaticamente]
           ↓
[Acompanhar morador até resolução]
```

---

## 5. FLUXO: ONBOARDING NOVO MORADOR

```
[Número desconhecido envia mensagem]
           ↓
[Verificar na tabela residents]
           ↓ Não encontrado
[Boas-vindas + coleta de dados]:

"👋 Olá! Sou a *Syndra*, assistente do 
Residencial Nogueira Martins.

Parece que é sua primeira vez aqui! 
Para que eu possa te ajudar melhor, 
preciso de algumas informações:

1️⃣ Qual é o seu nome?
2️⃣ Qual é o número do seu apartamento?
3️⃣ Você é proprietário(a) ou inquilino(a)?"
           ↓
[Cadastrar na tabela residents]
           ↓
[Enviar mensagem de apresentação completa]
           ↓
[Fluxo normal]
```

---

## 6. FLUXO: COMUNICADO DA ADMINISTRAÇÃO (Broadcast)

```
[Admin cria announcement via painel]
           ↓
[Syndra agenda ou envia imediatamente]
           ↓
[Buscar todos os moradores ativos]
           ↓
[Filtrar por audience: todos/bloco/proprietários]
           ↓
[Enviar em lotes de 50 (anti-spam)]
           ↓
[Aguardar 1s entre cada envio]
           ↓
[Log de entrega por morador]

Formato da mensagem:
"📢 *AVISO DO CONDOMÍNIO*

{titulo}

{conteudo}

_Residencial Nogueira Martins_
_Administração_"
```

---

## 7. GERENCIAMENTO DE CONTEXTO DE CONVERSA

```python
# Janela de memória: últimas 10 trocas da sessão atual
# Sessão expira após: 30 minutos de inatividade

CONTEXT_CONFIG = {
    "max_messages": 10,         # Mensagens no contexto
    "session_timeout": 1800,    # 30 minutos em segundos
    "summary_threshold": 20,    # Resumir após 20 trocas
}

# Estrutura enviada ao LLM em cada chamada:
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    # Histórico recente (últimas 10 trocas)
    *conversation_history[-10:],
    # Mensagem atual
    {"role": "user", "content": current_message}
]
```
