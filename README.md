# GCP Datastore Latency Test (Library vs REST API)

Este repositório foi desenvolvido para realizar uma comparação prática de latência e tempo de inicialização (cold starts vs warm starts) ao se conectar ao GCP Datastore (Firestore no modo Datastore) de três formas distintas:
1. **`datastore-lib-app`**: Utilizando o SDK oficial Python mais antigo (`google-cloud-datastore==2.23.0`).
2. **`datastore-rest-app`**: Utilizando chamadas HTTP diretas à API REST nativa, sem qualquer biblioteca externa adicional (apenas `urllib` nativo do Python).
3. **`datastore-lib-updated-app`**: Utilizando a última versão disponível do SDK oficial Python (`google-cloud-datastore==2.25.0`), para comparar se novas versões trouxeram otimizações de inicialização.

Ambas as aplicações foram configuradas para usar um banco de dados não-padrão denominado **`datastore-id1`**.

---

## 🏗️ Estrutura do Repositório

```text
crun-datastore-latency/
├── README.md                      # Este arquivo explicativo
├── PLAN.md                        # Checklist do ciclo de desenvolvimento
├── deploy.sh                      # Script para deploy automatizado na região southamerica-east1
├── populate_datastore.py          # Script Python para popular dados de teste
├── populate_datastore.sh          # Script auxiliar para execução do populador
├── medir_cold_starts.py           # Script para analisar e calcular cold starts exatos da GCP
├── rodar_stress_test.py           # Script para teste de carga/estresse (2 min)
└── simple-latency-test/
    ├── datastore-lib-app/         # App usando SDK Datastore v2.23.0
    │   ├── Dockerfile
    │   ├── main.py
    │   └── requirements.txt
    ├── datastore-rest-app/        # App usando API REST pura via urllib
    │   ├── Dockerfile
    │   ├── main.py
    │   └── requirements.txt
    └── datastore-lib-updated-app/ # App usando SDK Datastore v2.25.0
        ├── Dockerfile
        ├── main.py
        └── requirements.txt
```

---

## 📊 Métricas Medidas

Cada aplicação retorna um objeto JSON contendo as seguintes métricas de telemetria simplificadas:

*   **`app_initialization_ms`**: Tempo total gasto desde o início do container (primeira instrução Python executada) até a prontidão completa do servidor WSGI para responder requisições (inclui a importação do SDK e a inicialização global dos clientes).
*   **`db_request_start_timestamp`**: Timestamp Unix exato (microsegundos) registrado imediatamente antes do disparo da requisição de lookup ao Datastore.
*   **`db_request_end_timestamp`**: Timestamp Unix exato (microsegundos) registrado após o recebimento e parse da resposta do Datastore.
*   **`db_request_duration_ms`**: Duração líquida medida da consulta ao Datastore (Subtração dos dois timestamps acima em milissegundos).

---

## 🔥 Warm-up Automático no Startup
As três aplicações realizam uma **consulta de warm-up ao banco de dados no momento da inicialização** (logo após os logs de boot do container e antes de ficarem prontas para receber tráfego). 

Isso pré-aquece as conexões TCP/SSL e os sockets gRPC internos, evitando que a primeira chamada de usuário sofra a penalidade dessas conexões secundárias. O warm-up gera logs detalhados e estruturados no seguinte formato:

```text
Warm-up DB request started! datetime: 2026-07-20T15:00:00.123456Z
Warm-up DB request completed! datetime: 2026-07-20T15:00:00.245678Z
Startup database warm-up query completed successfully!
```

---

## 🚀 Como Executar os Testes de Performance e Carga

### 1. Pré-requisitos
*   Um projeto GCP ativo com o Firestore no modo Datastore habilitado.
*   Um banco de dados nomeado chamado **`datastore-id1`** já criado no seu projeto GCP (`crun-datastore-latency`).
*   Ferramenta de linha de comando `gcloud` instalada e autenticada (`gcloud auth login`).

### 2. Popular a Base de Dados
Execute o script de população de dados para criar ou atualizar a entidade de teste (`LatencyTest/test-entity`) no banco `datastore-id1`:
```bash
chmod +x populate_datastore.sh
./populate_datastore.sh
```

### 3. Fazer o Deploy no Cloud Run
O script de deploy irá configurar automaticamente o projeto `crun-datastore-latency` e aplicar as seguintes restrições de arquitetura ideais para testes de estresse:
*   **Concorrência Máxima**: Limitada a **1 requisição paralela** por instância (`--concurrency=1`).
*   **Instâncias Máximas**: Limitadas a no máximo **5 instâncias** por serviço (`--max-instances=5`).

Rode o deploy manualmente com o comando:
```bash
chmod +x deploy.sh
./deploy.sh
```

---

## ⚡ Realizando o Teste de Estresse (Carga)

Para ver as instâncias escalarem ao limite e medir como as aplicações se comportam sob pressão concorrente, utilize o script de estresse nativo:

```bash
chmod +x rodar_stress_test.py
./rodar_stress_test.py
```

*   **O que ele faz?** Ele descobre dinamicamente as URLs dos 3 serviços ativos e bombardeia cada um com 10 conexões simultâneas concorrentes durante **2 minutos** (120 segundos). Com a concorrência limitada a 1, isso força o Cloud Run a escalar as 3 aplicações para o pico de 5 instâncias ativas cada.
*   **Acompanhamento em Tempo Real**: Exibe estatísticas de requisições de sucesso (`OK`), erros (`ERR`) e tempo decorrido ao vivo no terminal.

---

## 📈 Analisando Cold Starts com Precisão

O script `medir_cold_starts.py` é uma ferramenta de observabilidade extremamente avançada que interage diretamente com o **Google Cloud Logging** para calcular a latência líquida da infraestrutura do Cloud Run.

Ele mede a diferença exata entre o momento em que a GCP decide criar o container e o momento em que o código da aplicação fica pronto para responder.

### Como Executar:
```bash
chmod +x medir_cold_starts.py
./medir_cold_starts.py [opções]
```

### Parâmetros Disponíveis:
*   `--minutes` / `-m` *(Opcional)*: Define a janela de tempo histórica dos logs analisados. O padrão é `15` minutos (ideal para isolar apenas o teste de estresse que você acabou de rodar).

**Exemplos:**
```bash
# Analisar logs dos últimos 15 minutos (padrão):
./medir_cold_starts.py

# Analisar logs dos últimos 5 minutos:
./medir_cold_starts.py --minutes 5

# Analisar logs da última meia hora:
./medir_cold_starts.py -m 30
```

### 🛡️ Características de Robustez:
*   **Isolamento por `instanceId`**: O pareamento de início de máquina física e boot do app é chaveado pelo ID de instância de 64 caracteres gerado pela GCP, impossibilitando qualquer cruzamento de dados de instâncias paralelas.
*   **Filtro Antirruído**: Descarta instâncias com tempos inválidos ou orfãs, e filtra automaticamente logs de requisições HTTP para ler apenas logs puros de inicialização do ciclo de vida do container.