# GCP Datastore Latency Test (Library vs REST API)

Este repositório foi desenvolvido para realizar uma comparação prática de latência e tempo de inicialização (cold starts vs warm starts) ao se conectar ao GCP Datastore (Firestore no modo Datastore) de duas formas distintas:
1. **`datastore-lib-app`**: Utilizando o SDK oficial Python (`google-cloud-datastore==2.23.0`).
2. **`datastore-rest-app`**: Utilizando chamadas HTTP diretas à API REST nativa, sem qualquer biblioteca externa adicional (apenas `urllib` nativo do Python).

Ambas as aplicações foram configuradas para usar um banco de dados não-padrão denominado **`datastore-id1`**.

---

## 🏗️ Estrutura do Repositório

```text
crun-datastore-latency/
├── README.md                      # Este arquivo explicativo
├── PLAN.md                        # Checklist do ciclo de desenvolvimento
├── populate_datastore.sh          # Script Bash para inserir a entidade de teste via REST
├── deploy.sh                      # Script para deploy automatizado na região southamerica-east1
└── simple-latency-test/
    ├── datastore-lib-app/         # App usando SDK google-cloud-datastore
    │   ├── Dockerfile
    │   ├── main.py
    │   └── requirements.txt
    └── datastore-rest-app/        # App usando API REST pura via urllib
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

## 🚀 Como Executar os Testes

### 1. Pré-requisitos
*   Um projeto GCP ativo com o Firestore no modo Datastore habilitado.
*   Um banco de dados nomeado chamado **`datastore-id1`** já criado no seu projeto GCP.
*   Ferramenta de linha de comando `gcloud` instalada e autenticada (`gcloud auth login`).

### 2. Popular a Base de Dados
Execute o script de população de dados para criar ou atualizar a entidade de teste (`LatencyTest/test-entity`) no banco `datastore-id1` usando a API REST pura e suas credenciais de gcloud locais:
```bash
chmod +x populate_datastore.sh
./populate_datastore.sh
```

### 3. Fazer o Deploy no Cloud Run
O script de deploy irá associar automaticamente a permissão de leitura/gravação do Datastore (`roles/datastore.user`) para a Default Compute Service Account do Cloud Run, e fará o deploy de ambos os serviços na região **`southamerica-east1`**:
```bash
chmod +x deploy.sh
./deploy.sh
```

### 4. Analisar e Comparar a Latência

#### 🧪 Cold Start (Tempo de Inicialização)
Logo após o deploy (ou escalando os containers ativos para 0), envie uma requisição para as URLs informadas pelo final do script `deploy.sh`:

```bash
# Testar App com SDK Oficial
curl <LIBRARY_SERVICE_URL>

# Testar App com REST Puro
curl <REST_SERVICE_URL>
```
*Compare o campo `app_initialization_ms` no JSON. O app REST iniciará ordens de grandeza mais rápido por não carregar as pesadas dependências internas e pacotes de gRPC/Proto do SDK oficial.*

#### 🔥 Warm Start (Latência do Banco de Dados)
Envie requisições repetidas enquanto os containers estão ativos e compare o campo `db_request_duration_ms`:
*   O SDK oficial possui pools de conexão HTTP/2 gRPC pré-inicializados e reutilizados nas requisições subsequentes.
*   O REST puro faz chamadas HTTP individuais por requisição usando `urllib`.