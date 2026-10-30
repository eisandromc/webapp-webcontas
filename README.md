# Divisão de Contas

Aplicação web para dividir as contas da casa entre os moradores. Ela roda num computador de casa e pode ser usada também pelos celulares da mesma rede. Reúne os gastos do mês, importa as compras da fatura do cartão em PDF, calcula quanto cabe a cada pessoa e acompanha quem já acertou.

- **Backend:** Python, FastAPI, SQLAlchemy e SQLite.
- **Frontend:** React 19, TypeScript, Vite e TanStack Query, instalável como app (PWA).
- **Sem nuvem e sem login:** os dados ficam num arquivo SQLite no próprio computador.

---

## Sumário

- [Recursos](#recursos)
- [Como a divisão funciona](#como-a-divisão-funciona)
- [Requisitos](#requisitos)
- [Instalação e execução](#instalação-e-execução)
- [Primeiros passos](#primeiros-passos)
- [Importar faturas do cartão](#importar-faturas-do-cartão)
- [Importar a planilha antiga](#importar-a-planilha-antiga)
- [Dados, backup e scripts](#dados-backup-e-scripts)
- [Segurança](#segurança)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Estrutura do projeto](#estrutura-do-projeto)
- [API](#api)
- [Desenvolvimento e testes](#desenvolvimento-e-testes)
- [Limitações conhecidas](#limitações-conhecidas)

---

## Recursos

### Painel (`/`)

- Gastos por mês nos últimos meses cadastrados, com média mensal e variação em relação ao mês anterior.
- Maiores categorias de gasto e principais custos, com os estabelecimentos agrupados pelo nome.
- Custos recorrentes: os que aparecem em 3 meses ou mais.
- Oportunidades de economia: uma simulação de corte de 10% em alimentação e extras.
- Quanto cada pessoa deve: valor em aberto acumulado de cada participante e o total a receber pela fonte primária.

### Mês (`/mes/AAAA-MM`)

- Mostra como o total foi formado: **gastos + vales = total a dividir**.
- Um cartão por pessoa, com a parte dela, os descontos, o custo extra, o que já pagou, o que ainda deve e o acumulado em aberto.
- Lançamentos agrupados por categoria, com as contas parceladas separadas.
- Registro de gastos, descontos, vales e pagamentos, com a opção "Salvar e adicionar outro".
- Importação de uma ou mais faturas em PDF direto no mês, com revisão unificada dos itens.
- Ajuste do período financeiro do mês (a faixa de datas aceita para compras da fatura).
- Botão para fechar e reabrir o mês.
- **Extrato para impressão:** "Imprimir extrato" gera um documento no formato de fatura, com resumo, lançamentos, vales e descontos, pagamentos e o fechamento de cada pessoa.

### Contas (`/contas`)

- Lista os meses cadastrados com o total, a situação (em processamento, aguardando acerto ou pago) e a situação de cada pessoa.
- Permite cadastrar, editar, reabrir, imprimir e excluir meses. Só é possível excluir um mês aberto e sem registros.

### Lançamentos (`/lancamentos`)

- Mostra todos os gastos, vales, descontos e pagamentos de todos os meses.
- Tem filtros por mês, tipo e categoria, e busca por texto que ignora acentos e maiúsculas.

### Histórico (`/historico`)

- Resumo de cada mês agrupado por ano, com o total de cada pessoa.

### Configurações (`/configuracoes`)

- **Senha protegida:** a senha do PDF da fatura, guardada no cofre de credenciais do sistema operacional.
- **Pessoas:** cadastrar, renomear, ativar ou desativar, escolher a fonte primária e excluir.
- **Categorias:** criar, renomear, mudar a cor e excluir. A exclusão só é permitida se a categoria não estiver em uso.
- **Datas dos novos meses:** o dia inicial e o final do período financeiro padrão.
- **Importar planilha antiga:** importa o histórico de um arquivo `.xlsx`, com prévia antes de confirmar.
- **Meses:** fechar, reabrir, editar e excluir.
- **Banco de dados:** baixar backup, importar um banco, zerar os dados e ver o registro de operações (auditoria).

### Outros

- **Uso em vários aparelhos:** a barra lateral mostra o endereço para abrir o app em outros aparelhos da rede.
- **PWA:** dá para instalar no celular ou no computador. A interface fica em cache, mas os dados financeiros sempre vêm do servidor.
- **Layout responsivo**, com navegação inferior no celular. O app é testado contra rolagem horizontal e com verificação automática de acessibilidade (axe).

---

## Como a divisão funciona

| Conceito | Regra |
| --- | --- |
| **Mês de cobrança e mês de referência** | O mês `2026-11` cobra as contas de outubro/2026. A tela mostra "Contas de outubro de 2026". |
| **Período financeiro** | É a faixa de datas cujas compras da fatura entram no mês. O padrão vem de **Datas dos novos meses** e pode ser ajustado em cada mês. Contas parceladas entram sempre. |
| **Total a dividir** | Soma dos gastos, mais os vales, menos os descontos gerais. |
| **Divisão** | Cada mês guarda quem participa e o percentual de cada um. Por padrão, a divisão é igual entre as pessoas ativas. Centavos de arredondamento vão para a última pessoa. |
| **Vale** | Valor somado ao total antes da divisão. |
| **Desconto para todos** | Reduz o total antes da divisão. |
| **Desconto de uma pessoa** | Abate só do saldo dessa pessoa. Se for um desconto da fonte primária, vira custo extra dividido igualmente entre os demais. |
| **Fonte primária** | A pessoa que paga as contas e recebe os acertos dos outros. A parte dela conta como paga. A fonte primária é opcional. |
| **Pagamentos** | Abatem o saldo de quem pagou, no mês em que foram registrados. |
| **Saldo acumulado** | Só as dívidas passam para o mês seguinte. Crédito, quando alguém paga a mais, não é acumulado. |
| **Quem pagou** (num lançamento) | É só um registro de quem adiantou aquela compra. **Não entra no cálculo.** Para abater esse valor de alguém, registre um pagamento ou um desconto. |

### Situação do mês

- **Em processamento:** o mês está aberto.
- **Aguardando acerto:** o mês está fechado e alguém ainda não pagou.
- **Pago:** o mês está fechado e todos acertaram. Para indicar que alguém acertou, marque o acerto como recebido.

### Mês fechado e mudanças nas pessoas

- Num mês fechado não é possível lançar, editar ou excluir gastos, vales, descontos e pagamentos, nem importar faturas ou mudar o período. Marcar acertos como recebidos continua liberado. Reabra o mês para corrigir algo.
- Criar, ativar ou desativar pessoas e trocar a fonte primária afeta **só os meses abertos**. Os meses fechados preservam a divisão da época, por isso feche os meses já acertados.
- Uma pessoa desativada continua com 0% nos meses abertos em que tem registros, para que os pagamentos dela não sumam.
- Uma pessoa com registros ou que participa de meses fechados não pode ser excluída, só desativada.
- Abrir um mês só para consultar não grava nada. O mês passa a constar em **Contas** quando é cadastrado ou quando recebe o primeiro registro.

---

## Requisitos

- **Python 3.12 ou superior**
- **Node.js 20 ou superior**, necessário apenas para compilar a interface
- **Windows, macOS ou Linux**
- No Linux, a senha do PDF precisa de um serviço de cofre compatível com o Secret Service, como o GNOME Keyring ou o KWallet.

---

## Instalação e execução

### Jeito rápido

| Sistema | Comando |
| --- | --- |
| Windows | `start.bat` |
| macOS / Linux | `./start.sh` |

Na primeira execução, o script:

1. cria o ambiente Python em `.venv/` e instala as dependências;
2. compila a interface em `frontend/dist/`;
3. sobe o servidor em `http://localhost:8000` e abre o navegador.

A `.venv/` é criada na máquina de cada pessoa e não vai para o repositório. Nas execuções seguintes, o script reinstala as dependências sozinho quando o `backend/requirements.txt` muda, por exemplo depois de um `git pull`, ou quando a instalação anterior não terminou. Se o ambiente ficar corrompido, apague a pasta `.venv/` e rode o script de novo.

Sem argumento, o script mostra um menu (Iniciar, Reiniciar, Parar, Status) e inicia sozinho depois de 10 segundos. Também aceita os comandos diretamente:

```bash
./start.sh iniciar | parar | reiniciar | status     # ou start.bat ... no Windows
```

Para usar outra porta, defina `DIVISAO_PORT` antes de rodar o script, por exemplo `DIVISAO_PORT=8080 ./start.sh`.

### Instalação manual

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
pip install -r backend\requirements.txt
cd frontend
npm install
npm run build
cd ..
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

> Depois de mudar o código do frontend, rode `npm run build` de novo. O script só compila quando `frontend/dist/` não existe.

### Acesso pelo celular

Os outros aparelhos da mesma rede usam `http://IP-DO-COMPUTADOR:8000`. O endereço aparece na barra lateral do app. Pode ser preciso liberar a porta no firewall do computador.

---

## Primeiros passos

1. Em **Configurações → Pessoas**, ajuste os nomes. O app começa com "Ana" e "Bruno". Escolha também a **fonte primária**.
2. Em **Configurações → Senha protegida**, salve a senha do PDF da fatura. Isso só pode ser feito no computador servidor.
3. Em **Configurações → Datas dos novos meses**, defina o período financeiro padrão, por exemplo do dia 1 ao 31.
4. Em **Contas**, cadastre o mês. Ou simplesmente abra um mês e faça o primeiro lançamento: ele é cadastrado sozinho.
5. Em **Mês**, lance as contas, importe a fatura, registre vales, descontos e pagamentos.
6. Quando tudo estiver conferido, **feche o mês** e marque os acertos à medida que forem recebidos.

---

## Importar faturas do cartão

O leitor foi feito para a fatura **Ourocard** (Banco do Brasil) em PDF protegido por senha. Para outros layouts há um leitor genérico, menos preciso, que reconhece linhas no formato `DD/MM DESCRIÇÃO VALOR`.

1. **Envio:** no mês, em **Importar cartão**, envie um ou mais PDFs de até 15 MB cada.
2. **Revisão:**
   - Os itens chegam desmarcados, ordenados por data, e com uma categoria sugerida.
   - A sugestão vem de palavras-chave (mercado, Uber, energia…) ou das suas escolhas anteriores. Quando você muda a categoria de um estabelecimento, o app grava uma regra e passa a sugerir essa categoria nas próximas faturas.
   - Pagamentos da própria fatura aparecem sinalizados como "sugerido excluir".
   - Itens fora do período financeiro do mês não entram. A exceção são as parcelas, que entram sempre.
3. **Conferência:** o app compara a soma dos itens marcados com o total da fatura.
4. **Sem duplicação:**
   - Reenviar o mesmo PDF reaproveita a análise anterior.
   - Itens já salvos, com a mesma data, descrição, valor e parcela, aparecem como importados e são ignorados.
5. Opcionalmente, indique quem pagou a fatura. É só um registro, veja a tabela acima.

---

## Importar a planilha antiga

Em **Configurações → Importar planilha antiga**, envie um `.xlsx` de até 15 MB. O app mostra uma prévia (meses, registros e avisos), e nada é gravado até você confirmar. Reenviar a mesma planilha não duplica nada.

Formato esperado, com uma aba por mês chamada `AAAA-MM_Nome` (ex.: `2025-02_Fev`):

| Colunas | Conteúdo | Vira |
| --- | --- | --- |
| A/B | `LUZ`, `ÁGUA`, `GÁS`, `INTERNET`, `COND.` e valor | Gasto em **Contas** |
| D/E (da linha 4) | Descrição e valor | Gasto em **Alimentação**. Linhas `VALE…` viram vale, e `DESC VALE` vira desconto. |
| F/G (da linha 4) | Descrição e valor | Gasto em **Extras**. Depois de uma linha `TRANSPORTE`, os seguintes vão para **Transporte**. |
| I/J (da linha 6) | Descrição e valor | **Desconto** |

Linhas `PAGO…` e `FALTOU…` viram avisos para revisão manual, porque a planilha não diz quem pagou.

---

## Dados, backup e scripts

Tudo fica em `data/`, que não é versionado porque contém dados pessoais:

| Arquivo | Conteúdo |
| --- | --- |
| `data/contas.db` | Banco principal (SQLite). Os arquivos `-wal` e `-shm` ao lado fazem parte dele. |
| `data/auditoria.db` | Registro de backups, importações de banco, resets e exclusões de mês. Esse registro sobrevive a resets e restaurações. |
| `data/backups/` | Cópias criadas pelo app e pelos scripts. |

Fora de `data/`:

- **Senha do PDF:** fica no cofre do sistema (Gerenciador de Credenciais do Windows, Chaves do macOS ou Secret Service no Linux). Ela não vai junto num backup; numa máquina nova, salve-a de novo.
- **Faturas e planilhas enviadas:** não são guardadas. O app lê o conteúdo em memória e grava só os lançamentos.

### Backup e restauração

- **Backup:** em **Configurações → Banco de dados → Fazer backup**, o app baixa uma cópia consistente, que pode ser feita com o servidor ligado. Com o servidor parado, também basta copiar `data/contas.db`.
- **Restauração:** em **Importar banco**, envie um `.db`. O app valida o arquivo e faz uma cópia de segurança do banco atual antes de substituí-lo.
- O esquema do banco é atualizado automaticamente na inicialização, então bancos antigos continuam funcionando.

### Scripts

| Script | O que faz |
| --- | --- |
| `python scripts/zerar_banco.py` | Apaga lançamentos, vales, descontos, pagamentos, faturas, importações e acertos, e reabre os meses. Mantém pessoas, categorias, meses e configurações. |
| `python scripts/zerar_banco.py --tudo` | Apaga tudo e recria o cadastro inicial. |

O `zerar_banco.py` pede que você digite `ZERAR` (use `--sim` para pular a confirmação) e sempre cria uma cópia em `data/backups/` antes de apagar.

---

## Segurança

O app **não tem login**: quem acessa a rede usa o app. Por isso:

- Use apenas numa rede doméstica confiável e **não exponha a porta à internet**.
- **Operações sensíveis:** salvar ou remover a senha do PDF, baixar backup, importar banco e zerar dados só funcionam no próprio computador servidor (`localhost`).
- **Gravações de outros sites:** o servidor recusa gravações que venham de outros sites, o que impede que uma página maliciosa aberta no navegador altere os dados.
- **Endereços aceitos:** só IPs, `localhost` e o nome desta máquina. Isso evita ataques de *DNS rebinding*. Para liberar outro nome, use `DIVISAO_ALLOWED_HOSTS`.
- **Senha do PDF:** nunca é gravada no SQLite nem devolvida pela API.

---

## Variáveis de ambiente

| Variável | Padrão | Uso |
| --- | --- | --- |
| `DIVISAO_PORT` | `8000` | Porta usada por `start.bat` e `start.sh`. |
| `DIVISAO_DATA_DIR` | `data/` | Pasta dos dados. |
| `DIVISAO_DB` | `$DIVISAO_DATA_DIR/contas.db` | Caminho do banco principal. |
| `DIVISAO_BACKUP_DIR` | `<pasta do banco>/backups` | Pasta dos backups. |
| `DIVISAO_AUDIT_DB` | `<pasta do banco>/auditoria.db` | Banco de auditoria. |
| `DIVISAO_ALLOWED_HOSTS` | (vazio) | Nomes de host extras aceitos, separados por vírgula. |

---

## Estrutura do projeto

```text
├── start.bat / start.sh          # iniciar, parar, reiniciar e status do servidor
├── backend/
│   ├── requirements.txt          # dependências de produção
│   ├── requirements-dev.txt      # + pytest e httpx
│   └── app/
│       ├── main.py               # app FastAPI, serve a API e a interface compilada
│       ├── config.py             # caminhos e limites (variáveis DIVISAO_*)
│       ├── seed.py               # pessoas e categorias iniciais
│       ├── api/
│       │   ├── routers/          # endpoints por assunto (meses, registros, faturas…)
│       │   ├── schemas.py        # validação das requisições (Pydantic)
│       │   └── security.py       # filtro de host/origem e operações só no servidor
│       ├── db/                   # modelos SQLAlchemy e atualização do esquema
│       ├── domain/calc.py        # cálculo puro da divisão, em centavos inteiros
│       └── services/             # regras de negócio: meses, faturas, painel, backup,
│                                 # leitura de PDF e planilha, cofre de senha
├── frontend/
│   ├── src/
│   │   ├── features/             # telas: painel, mês, contas, lançamentos, histórico,
│   │   │                         # fatura, configurações
│   │   ├── components/           # layout, modais, diálogos, ícones
│   │   └── api.ts                # chamadas à API e formatação de valores e datas
│   ├── public/                   # ícones, manifest e service worker (PWA)
│   └── tests/e2e/                # testes Playwright
├── scripts/                      # zerar banco
├── tests/backend/                # testes pytest
└── data/                         # banco e backups (não versionado)
```

---

## API

Todas as rotas ficam sob `/api` e usam JSON. Valores monetários são **centavos inteiros** (`amount_cents`) e meses usam o formato `AAAA-MM`. Com o servidor rodando, a documentação interativa fica em `http://localhost:8000/docs`.

| Área | Rotas principais |
| --- | --- |
| Sistema | `GET /health`, `GET /bootstrap`, `GET /server-info` |
| Pessoas | `GET/POST /people`, `PATCH/DELETE /people/{id}` |
| Meses | `GET/POST /months`, `GET /months/suggestion`, `GET/PATCH/DELETE /months/{period}`, `PUT /months/{period}/range`, `/closed`, `/shares`, `/settlements/{person_id}`, `GET /accounts` |
| Registros | `POST /months/{period}/entries`, `/adjustments`, `/payments`; `PATCH/DELETE /entries/{id}`, `/adjustments/{id}`, `/payments/{id}` |
| Categorias | `GET/POST /categories`, `PATCH/DELETE /categories/{slug}` |
| Relatórios | `GET /history`, `GET /ledger`, `GET /dashboard` |
| Faturas | `POST /invoices/analyze`, `GET /invoice-drafts/{id}`, `PATCH /invoice-drafts/{id}/items/{item_id}`, `POST /invoice-drafts/{id}/import` |
| Planilha | `POST /imports/spreadsheet?commit=false\|true`, `GET /imports/issues` |
| Configurações | `GET/PUT/DELETE /settings/pdf-password`, `GET/PUT /settings/period-defaults` |
| Banco | `GET /backups`, `GET /backup/download`, `POST /backup/import`, `POST /backup/reset`, `GET /audit-log` |

---

## Desenvolvimento e testes

```powershell
pip install -r backend\requirements-dev.txt

# backend com recarga automática
python -m uvicorn app.main:app --app-dir backend --reload --port 8000

# frontend com recarga automática em http://localhost:5173 (as chamadas /api vão para a porta 8000)
cd frontend
npm run dev
```

Testes:

```powershell
pytest -q tests\backend        # regras de cálculo, meses, leitor de PDF e planilha, segurança
cd frontend
npm run build                  # checagem de tipos (tsc) e build
npm run e2e                    # Playwright no Chrome: desktop e celular, acessibilidade
```

- **Testes e2e isolados:** os testes e2e sobem um servidor próprio na porta 8010, com um banco descartável em `frontend/test-results/e2e-data/`. O `data/contas.db` nunca é usado.
- **Pré-requisitos do e2e:** o Google Chrome instalado e a interface compilada (`npm run build`).
- **Convenções do código:**
  - Dinheiro é sempre em centavos inteiros, nunca em ponto flutuante.
  - O cálculo da divisão fica em `domain/calc.py`, sem acesso ao banco.
  - As rotas só validam a entrada e chamam os serviços.

---

## Limitações conhecidas

- **Leitura de faturas:** só o layout Ourocard é lido com alta precisão; os outros dependem do leitor genérico.
- **Quem pagou:** o campo "Quem pagou" dos lançamentos é informativo e não altera o cálculo.
- **Saldo acumulado:** créditos (pagamentos acima do devido) não passam para o mês seguinte.
- **Percentuais:** a divisão por percentuais diferentes existe na API (`PUT /months/{period}/shares`), mas ainda não tem tela.
- **Usuários:** não há controle de acesso por usuário.
