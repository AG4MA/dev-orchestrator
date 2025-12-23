"# Dev Orchestrator

**Orchestratore multi-agente per accelerare lo sviluppo su repository target.**

Sistema LangChain + LangGraph con OpenAI per orchestrare agenti AI nel pattern 1-N-1.

## 🎯 Obiettivo

Dev Orchestrator è un sistema che orchestra agenti AI per eseguire task di sviluppo su un repository target in modo controllato, ripetibile e auditabile.

**Principi fondamentali:**
- ✅ Mai modificare main/master direttamente
- ✅ Ogni modifica su branch dedicato
- ✅ Ogni esecuzione produce log e report
- ✅ Nessun segreto nel codice
- ✅ Output sempre verificabile

## 🤖 Pattern Multi-Agente (1-N-1)

```
                    ┌─────────────────┐
                    │    Architect    │  ← Phase 1: Analyze & Design
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
    ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
    │ Implementer │   │   Tester    │   │ Documenter  │  ← Phase N: Parallel
    └──────┬──────┘   └──────┬──────┘   └──────┬──────┘
           │                 │                 │
           └─────────────────┼─────────────────┘
                             │
                    ┌────────▼────────┐
                    │    Reviewer     │  ← Phase 1: Aggregate & Validate
                    └─────────────────┘
```

## 📦 Installazione

### Prerequisiti

- Python 3.11+
- Git installato e configurato
- **OpenAI API Key** (per il comando `agents`)

### Setup

```powershell
# Clona o naviga al repository
cd c:\projects\dev-orchestrator

# Crea virtual environment
python -m venv .venv

# Attiva virtual environment (PowerShell)
.\.venv\Scripts\Activate.ps1

# Installa in modalità sviluppo
pip install -e ".[dev]"
```

### Configurazione OpenAI

```powershell
# Copia il template
cp .env.example .env

# Modifica .env con la tua API key
# OPENAI_API_KEY=sk-your-key-here
```

### Verifica installazione

```powershell
# Verifica CLI
orchestrator --version

# Mostra configurazione
orchestrator config
```

## 🚀 Utilizzo

### Comando Multi-Agente: `agents` (LLM-powered)

Esegue un'orchestrazione multi-agente con LangChain/OpenAI.

```powershell
orchestrator agents --repo <path-al-repo> --goal "<obiettivo>"
```

**Esempio:**

```powershell
orchestrator agents --repo C:\projects\my-software --goal "Aggiungi una healthcheck endpoint e test basilari"
```

**Cosa fa:**
1. **Architect** analizza la codebase e progetta la soluzione
2. **Implementer**, **Tester**, **Documenter** lavorano in parallelo
3. **Reviewer** aggrega e valida i cambiamenti
4. Applica le modifiche e crea commit su branch dedicato

**Opzioni:**

| Flag | Descrizione |
|------|-------------|
| `--repo, -r` | Percorso al repository target (obbligatorio) |
| `--goal, -g` | Obiettivo da raggiungere (obbligatorio) |
| `--model, -m` | Override modello (es. gpt-4o) |
| `--verbose` | Output dettagliato |

### Comando Legacy: `run`

Esecuzione senza LLM (regole hardcoded).

```powershell
orchestrator run --repo <path-al-repo> --goal "<obiettivo>"
```

**Opzioni:**

| Flag | Descrizione |
|------|-------------|
| `--repo, -r` | Percorso al repository target (obbligatorio) |
| `--goal, -g` | Obiettivo da raggiungere (obbligatorio) |
| `--dry-run, -n` | Solo pianificazione, senza modifiche |
| `--verbose` | Output dettagliato |

### Altri comandi

```powershell
# Lista tutte le esecuzioni
orchestrator list

# Stato di una specifica esecuzione
orchestrator status <run_id>

# Visualizza report di una esecuzione
orchestrator report <run_id>

# Mostra configurazione
orchestrator config
```

## 📁 Struttura del Progetto

```
dev-orchestrator/
├── src/
│   └── dev_orchestrator/
│       ├── __init__.py
│       ├── cli.py                 # Entrypoint CLI (Typer + Rich)
│       ├── core/
│       │   ├── config.py          # Configurazione
│       │   ├── run_context.py     # Stato della run
│       │   ├── git_ops.py         # Operazioni Git sicure
│       │   ├── llm_config.py      # Configurazione OpenAI
│       │   ├── planner.py         # Goal → Task list
│       │   ├── executor.py        # Coordinatore (legacy)
│       │   └── roles/             # Ruoli hardcoded (legacy)
│       └── agents/
│           ├── base_agent.py      # BaseAgent + AgentOutput + AgentState
│           ├── architect_agent.py # Fase 1: Analisi e design
│           ├── implementer_agent.py # Fase N: Codice
│           ├── tester_agent.py    # Fase N: Test
│           ├── documenter_agent.py # Fase N: Documentazione
│           ├── reviewer_agent.py  # Fase 1: Review finale
│           ├── workflow.py        # LangGraph workflow 1-N-1
│           └── agent_executor.py  # Coordinatore multi-agente
├── tests/                         # Test pytest
├── templates/                     # Template per report
├── runs/                          # Artefatti delle run (ignorato da git)
├── .env.example                   # Template variabili d'ambiente
├── pyproject.toml
└── README.md
```

## 🔄 Workflow di una Run

1. **Setup**: Validazione repository target
2. **Planning**: Decomposizione goal in task list
3. **Branch**: Creazione branch dedicato (`orchestrator/<data>/<slug>`)
4. **Execution**: Esecuzione sequenziale dei task per ruolo
5. **Apply**: Applicazione delle modifiche proposte
6. **Commit**: Commit delle modifiche
7. **Report**: Generazione report finale

### Ruoli

| Ruolo | Responsabilità |
|-------|----------------|
| **Architect** | Analisi codebase, design soluzione, review |
| **Implementer** | Scrittura/modifica codice |
| **Tester** | Esecuzione test, validazione |
| **Documenter** | Aggiornamento documentazione |

## ⚙️ Configurazione

### Variabili OpenAI (per comando `agents`)

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `OPENAI_API_KEY` | - | **Obbligatoria** - API key OpenAI |
| `OPENAI_MODEL` | `gpt-4o-mini` | Modello da usare |
| `OPENAI_TEMPERATURE` | `0.2` | Temperatura (creatività) |
| `OPENAI_MAX_TOKENS` | `4096` | Max token per risposta |
| `OPENAI_TIMEOUT` | `60` | Timeout in secondi |

### Variabili Orchestrator

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `ORCHESTRATOR_DRY_RUN` | `false` | Modalità dry-run globale |
| `ORCHESTRATOR_DEFAULT_BRANCH` | `main` | Branch default |
| `ORCHESTRATOR_BRANCH_PREFIX` | `orchestrator` | Prefisso branch |
| `ORCHESTRATOR_ALLOW_PUSH` | `false` | Abilita push remoto |
| `ORCHESTRATOR_VERBOSE` | `false` | Output verboso |

## 🧪 Test

```powershell
# Esegui tutti i test
pytest

# Con copertura
pytest --cov=dev_orchestrator

# Solo test specifici
pytest tests/test_planner.py -v
```

## 📝 Esempio Completo

### Scenario

Repository target: `C:\projects\my-api`  
Goal: "Aggiungi una healthcheck endpoint e test basilari"

### Esecuzione

```powershell
# Esegui orchestrazione
orchestrator run --repo C:\projects\my-api --goal "Aggiungi una healthcheck endpoint e test basilari"
```

### Output atteso

```
╭─────────────────────────────────────────╮
│        Dev Orchestrator v0.1.0          │
│      Agentic Development Workflow       │
╰─────────────────────────────────────────╯

Run Configuration
Repository    C:\projects\my-api
Goal          Aggiungi una healthcheck endpoint e test basilari
Dry Run       No

Run ID: run_20241223_143000_a1b2c3d4

✓ Setup complete
✓ Plan created (5 tasks)
✓ Branch created: orchestrator/20241223/healthcheck-endpoint-test
✓ Tasks executed
✓ Applied 2 file(s)
✓ Changes committed
✓ Report generated

Run Summary
Run ID          run_20241223_143000_a1b2c3d4
Status          completed
Branch          orchestrator/20241223/healthcheck-endpoint-test
Tasks           5
Files Modified  2
Errors          0

✓ Run completed successfully!
Report: C:\projects\dev-orchestrator\runs\run_20241223_143000_a1b2c3d4\report.md
```

### Artefatti generati

```
runs/run_20241223_143000_a1b2c3d4/
├── state.json     # Stato completo della run
├── plan.json      # Piano di esecuzione
└── report.md      # Report finale
```

### Branch creato nel repo target

```
orchestrator/20241223/healthcheck-endpoint-test
```

### File modificati nel repo target

```
my-api/
├── src/
│   └── health.py        # NUOVO: Healthcheck module
└── tests/
    └── test_health.py   # NUOVO: Test per healthcheck
```

## 🔒 Sicurezza

- **Branch protetti**: main, master, develop, production non sono modificabili direttamente
- **No force push**: Mai forzatura su branch esistenti
- **No segreti**: Nessun token/password nel codice, solo variabili d'ambiente
- **Audit trail**: Ogni run è tracciata con timestamp e log completi

## 🛣️ Roadmap MVP

- [x] Struttura progetto base
- [x] CLI con Typer + Rich
- [x] Operazioni Git sicure
- [x] Planner goal → task
- [x] Ruoli base (architect, implementer, tester, documenter)
- [x] Executor con coordinamento
- [x] Report generation
- [x] Test base
- [ ] Integrazione LLM per proposte intelligenti
- [ ] PR creation (GitHub/GitLab API)
- [ ] Rollback automatico

## 📄 Licenza

MIT

---

*Dev Orchestrator v0.1.0 - Agentic Development Workflow*" 
