# PRD — Syndra Agent
## Product Requirements Document
**Produto:** Syndra — IA de Gestão do Residencial Nogueira Martins  
**Versão:** 1.0  
**Data:** Março 2025  
**Status:** Em Desenvolvimento

---

## 1. Visão Geral do Produto

### 1.1 Problema
Condomínios residenciais enfrentam gargalos recorrentes de comunicação: moradores não sabem a quem recorrer, chamados de manutenção se perdem, reservas de espaços geram conflitos e comunicados da administração chegam tarde ou são igsyndrados. O síndico e o zelador ficam sobrecarregados com demandas repetitivas que poderiam ser resolvidas de forma automatizada.

### 1.2 Solução
A **Syndra** é uma assistente de inteligência artificial que opera via WhatsApp, disponível 24 horas por dia, capaz de resolver autonomamente as demandas mais comuns do condomínio — e escalar para humanos apenas quando necessário.

### 1.3 Proposta de Valor
- **Para o morador:** atendimento imediato, sem fila, no canal que já usa.
- **Para o síndico:** menos interrupções, rastreabilidade total de chamados e reservas.
- **Para a administração:** comunicação centralizada, histórico persistente e métricas de uso.

---

## 2. Objetivos e Métricas de Sucesso

| Objetivo | Métrica | Meta (90 dias) |
|---|---|---|
| Reduzir chamadas ao síndico | % de demandas resolvidas pela Syndra sem escalação | ≥ 70% |
| Agilidade no atendimento | Tempo médio de primeira resposta | < 30 segundos |
| Adoção pelos moradores | % de unidades que interagiram ao menos 1x | ≥ 60% |
| Satisfação do morador | NPS pós-atendimento (survey mensal) | ≥ 7,5 |
| Confiabilidade | Uptime do sistema | ≥ 99,5% |

---

## 3. Usuários e Personas

### Persona 1 — Morador Típico
- **Perfil:** 30–60 anos, usa WhatsApp diariamente, pouca tolerância a burocracia.
- **Dores:** não sabe o número do zelador, perde comunicados, não consegue reservar o salão facilmente.
- **Necessidade:** resolver sua demanda com o mínimo de esforço, no celular.

### Persona 2 — Síndico
- **Perfil:** morador eleito voluntariamente, acumula a função com sua rotina profissional.
- **Dores:** recebe mensagens fora de hora, perde histórico de chamados, não tem visibilidade do que está pendente.
- **Necessidade:** ser acionado apenas em casos que exigem sua decisão.

### Persona 3 — Administradora do Condomínio
- **Perfil:** empresa terceirizada ou síndico profissional.
- **Dores:** comunicação descentralizada, dificuldade em disseminar avisos.
- **Necessidade:** canal único e rastreável para comunicados e gestão de demandas.

---

## 4. Escopo do Produto

### 4.1 Incluído no V1

| Funcionalidade | Descrição |
|---|---|
| Onboarding de moradores | Cadastro automático via WhatsApp na primeira mensagem |
| Atendimento a dúvidas | Consulta ao regimento interno via RAG (busca semântica) |
| Abertura de chamados | Triagem, protocolo automático e notificação do zelador |
| Reserva de espaços | Verificação de disponibilidade, pré-reserva e confirmação pós-pagamento |
| Broadcast de avisos | Envio de comunicados da administração para todos ou grupos de moradores |
| Escalação automática | Detecção de emergências e notificação imediata ao síndico |
| Histórico persistente | Todas as conversas salvas no Supabase com sessão de 30 minutos |

### 4.2 Fora do Escopo (V1)
- Painel web administrativo (previsto para V2)
- Integração com boletos bancários (previsto para V2)
- App mobile próprio
- Suporte a múltiplos condomínios na mesma instância
- Votações de assembleia online

---

## 5. Requisitos Funcionais

### RF-01: Cadastro de Moradores
- O sistema deve identificar o número de WhatsApp do remetente.
- Se o número não estiver cadastrado, iniciar fluxo de onboarding.
- Coletar: nome completo, número do apartamento, bloco, tipo (proprietário/inquilino).
- Salvar na tabela `residents` do Supabase.

### RF-02: Atendimento a Dúvidas (RAG)
- O sistema deve gerar embeddings da mensagem do morador.
- Realizar busca semântica na tabela `knowledge_chunks` (pgvector).
- Retornar resposta fundamentada no regimento interno com citação da fonte.
- Threshold mínimo de similaridade: 0,75.

### RF-03: Gestão de Manutenção
- O sistema deve classificar o problema em: Elétrica, Hidráulica, Estrutural, Equipamento, Limpeza ou Outro.
- Triagem de urgência: P1 (≤2h), P2 (≤24h), P3 (≤72h).
- Gerar protocolo único no formato `MNT-AAAA-NNNN`.
- Notificar zelador via WhatsApp ao abrir chamado P1 ou P2.
- Permitir consulta de status pelo morador via protocolo.

### RF-04: Reservas de Espaços
- Espaços gerenciados: Salão de Festas, Churrasqueira, Quadra, Academia.
- Verificar disponibilidade em tempo real (constraint UNIQUE no banco).
- Criar pré-reserva com status `pendente` e informar valor e chave Pix.
- Confirmar reserva automaticamente após recebimento do comprovante (manual V1 / automático V2).
- Enviar lembrete 24h antes da data reservada.

### RF-05: Broadcast de Comunicados
- Administrador envia comunicado via endpoint `/admin/broadcast` (autenticado por API Key).
- Sistema filtra moradores por audiência: `todos`, `bloco_a`, `proprietarios`, etc.
- Envio em lotes de 50 com intervalo de 1 segundo entre mensagens (anti-spam WhatsApp).
- Registrar status de envio por morador.

### RF-06: Escalação e Emergências
- Detectar palavras-chave de emergência (incêndio, inundação, arrombamento, etc.).
- Ativar Modo Urgência: resposta imediata + notificação ao síndico com nível URGENTE.
- Abrir chamado P1 automaticamente.
- Fornecer contatos de emergência (bombeiros, SAMU, portaria) na resposta.

---

## 6. Requisitos Não-Funcionais

| Requisito | Especificação |
|---|---|
| Disponibilidade | 99,5% uptime (≤ 3,6h de downtime/mês) |
| Latência | Primeira resposta ao morador em ≤ 30 segundos |
| Segurança | HTTPS obrigatório, RLS no Supabase, rate limiting (10 msg/min por número) |
| Privacidade | Conformidade com LGPD; dados pessoais jamais compartilhados entre moradores |
| Escalabilidade | Suportar até 200 unidades sem alteração de arquitetura |
| Manutenibilidade | Código documentado, variáveis de ambiente externalizadas, logs estruturados |

---

## 7. Arquitetura Resumida

```
WhatsApp ──► Evolution API v2 ──► FastAPI (Syndra App)
                                        │
                          ┌─────────────┼─────────────┐
                          │             │             │
                    OpenRouter/etc.  Supabase       Redis
                   (LLM + Tools)  (DB + RAG)    (Cache)
```

**Stack:** Python 3.11 · FastAPI · OpenRouter / OpenAI / Gemini · Supabase (PostgreSQL + pgvector) · Evolution API v2 · Redis · Docker · Nginx · Ubuntu 22.04 LTS

---

## 8. Fluxos Principais

### 8.1 Mensagem Recebida (Happy Path)
1. Morador envia mensagem no WhatsApp.
2. Evolution API dispara webhook para FastAPI.
3. Sistema identifica/cadastra o morador.
4. Recupera histórico de conversa (últimas 10 trocas).
5. Busca contexto relevante na base de conhecimento (RAG).
6. LLM processa com system prompt + tools disponíveis.
7. Executa tool calls necessários (Supabase, notificações).
8. Resposta enviada ao morador em ≤ 30 segundos.
9. Conversa salva no histórico.

### 8.2 Emergência Detectada
1. Mensagem com palavra-chave de emergência recebida.
2. Sistema ativa Modo Urgência imediatamente.
3. Resposta ao morador com orientações e contatos.
4. Notificação simultânea ao síndico e zelador via WhatsApp.
5. Chamado P1 aberto automaticamente.

---

## 9. Dependências e Integrações

| Serviço | Finalidade | Tipo |
|---|---|---|
| OpenRouter / OpenAI / Gemini | Geração de linguagem e raciocínio | Externo (pago) |
| Supabase | Banco de dados, vetores e storage | Externo (freemium) |
| Evolution API v2 | Gateway WhatsApp | Self-hosted (VPS) |
| Redis | Cache de sessão e filas | Self-hosted (VPS) |
| Let's Encrypt | Certificado SSL | Externo (gratuito) |

---

## 10. Plano de Lançamento

### Fase 1 — Setup (Semana 1–2)
- [ ] Provisionar VPS e executar `setup_vps.sh`
- [ ] Configurar domínio e SSL
- [ ] Executar `schema.sql` no Supabase
- [ ] Conectar WhatsApp via Evolution API (QR Code)
- [ ] Popular base de conhecimento (`seed_knowledge.py`) com regimento e FAQ

### Fase 2 — Testes Internos (Semana 3)
- [ ] Testar todos os fluxos com número de teste
- [ ] Validar RAG com perguntas reais de moradores
- [ ] Ajustar system prompt com base nos resultados
- [ ] Testar fluxo de emergência e notificação ao síndico

### Fase 3 — Lançamento Piloto (Semana 4)
- [ ] Apresentar a Syndra para o síndico e administração
- [ ] Enviar mensagem de apresentação no grupo do condomínio
- [ ] Monitorar logs e corrigir problemas em tempo real
- [ ] Coletar feedback dos primeiros moradores

### Fase 4 — Go-Live Completo (Mês 2)
- [ ] Ajustes baseados no piloto
- [ ] Treinamento do síndico para usar o endpoint de broadcast
- [ ] Documentação de uso para moradores (1 página)
- [ ] Início da coleta de NPS mensal

---

## 11. Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| WhatsApp banir o número por spam | Média | Alto | Envio em lotes + delays + Evolution API homologada |
| Respostas incorretas da IA | Média | Médio | RAG com threshold alto + revisão periódica da base |
| VPS fora do ar | Baixa | Alto | Monitoramento com alertas + restart automático Docker |
| Moradores resistentes à IA | Média | Médio | Onboarding claro + opção de falar com síndico sempre disponível |
| Dados sensíveis vazados | Baixa | Crítico | RLS Supabase + sem cross-data entre moradores + auditoria |

---

## 12. Critérios de Aceite (Definition of Done)

O produto estará pronto para go-live quando:

- [ ] Todos os 6 fluxos principais funcionando sem erros em ambiente de produção
- [ ] Tempo de resposta médio ≤ 30 segundos em condições normais
- [ ] Base de conhecimento populada com regimento interno completo
- [ ] Sistema de emergência testado e síndico notificado corretamente
- [ ] Logs funcionando sem erros críticos por 48h consecutivas
- [ ] Síndico treinado e aprovando o comportamento da Syndra

---

*Documento mantido pela equipe de desenvolvimento do Residencial Nogueira Martins.*
