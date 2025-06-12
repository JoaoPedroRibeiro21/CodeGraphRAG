# Chat com Documentos - Sistema RAG

## Estrutura do Projeto

```
projeto/
├── app.py                          # Aplicação Flask principal
├── templates/
│   └── index.html                  # Interface front-end
├── files/
│   └── Apresentacao2025.pdf        # Documento PDF para consulta
├── arquivos/
│   └── chat_retrieval_db/          # Banco de dados vetorial (criado automaticamente)
├── requirements.txt                # Dependências Python
└── README.md                       # Este arquivo
```

## Instalação e Configuração

### 1. Instalar Dependências

```bash
pip install flask flask-cors langchain langchain-openai langchain-community chromadb pypdf python-dotenv
```

### 2. Configurar Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
OPENAI_API_KEY=sua_chave_openai_aqui
```

### 3. Estrutura de Diretórios

Certifique-se de criar os diretórios necessários:

```bash
mkdir templates files arquivos
```

### 4. Adicionar o Documento

Coloque seu arquivo PDF em `files/Apresentacao2025.pdf`

## Como Executar

1. Execute a aplicação Flask:
```bash
python app.py
```

2. Acesse no navegador:
```
http://localhost:5000
```

## Funcionalidades

### API Endpoints

- **GET /** - Interface web principal
- **POST /perguntar** - Endpoint para fazer perguntas ao documento
- **GET /status** - Verifica o status do sistema
- **GET /health** - Health check da aplicação

### Interface Web

- Chat interativo com o documento
- Indicador de status do sistema
- Interface responsiva para desktop e mobile
- Animações suaves e feedback visual
- Tratamento de erros

## Exemplo de Uso da API

### Fazer uma Pergunta

```javascript
const response = await fetch('/perguntar', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        pergunta: "Qual é o tema principal do documento?"
    })
});

const data = await response.json();
console.log(data.resposta);
```

### Verificar Status

```javascript
const response = await fetch('/status');
const data = await response.json();
console.log(data);
// { "status": "ativo", "sistema_inicializado": true }
```

## Melhorias Implementadas

### No Backend (app.py):

1. **Tratamento de Erros**: Sistema robusto de tratamento de exceções
2. **Validação de Entrada**: Verificação de dados JSON e parâmetros
3. **Inicialização Segura**: Verifica se arquivos existem antes de processar
4. **Endpoints Adicionais**: Status e health check
5. **CORS Configurado**: Permite requisições do front-end
6. **Logging**: Mensagens informativas sobre o estado do sistema

### No Frontend:

1. **Interface Moderna**: Design responsivo com gradientes e animações
2. **Chat Interativo**: Experiência similar a aplicações de chat modernas
3. **Indicadores Visuais**: Status do sistema, loading, erros
4. **Responsividade**: Funciona bem em desktop e mobile
5. **Tratamento de Erros**: Mensagens claras para o usuário
6. **Auto-resize**: Campo de entrada se adapta ao conteúdo
7. **Atalhos de Teclado**: Enter para enviar, Shift+Enter para nova linha

## Troubleshooting

### Problemas Comuns:

1. **Arquivo PDF não encontrado**: Verifique se o arquivo está em `files/Apresentacao2025.pdf`
2. **Erro de API Key**: Configure a variável de ambiente `OPENAI_API_KEY`
3. **Dependências**: Execute `pip install -r requirements.txt`
4. **Porta ocupada**: Mude a porta no `app.run(port=XXXX)`

### Logs Úteis:

O sistema exibe mensagens no console sobre:
- Status de inicialização
- Carregamento de documentos
- Erros de processamento
- Status das requisições

## Personalização

### Modificar o Prompt:

Edite a variável `prompt_template` no arquivo `app.py` para personalizar as respostas.

### Adicionar Mais Documentos:

Modifique a lista `caminhos` no arquivo `app.py` para incluir mais PDFs.

### Customizar Interface:

Edite o CSS no arquivo `templates/index.html` para modificar a aparência.

## Segurança

- Configure CORS adequadamente para produção
- Use HTTPS em produção
- Mantenha a API Key segura
- Considere autenticação para acesso à API