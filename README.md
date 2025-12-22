"# Dev Orchestrator

**Orchestratore agentico per accelerare lo sviluppo su repository target.**

Produce solo artefatti verificabili: branch, commit, report, checklist.

## 🎯 Obiettivo

Dev Orchestrator è un sistema che orchestra "ruoli agentici" per eseguire task di sviluppo su un repository target in modo controllato, ripetibile e auditabile.

**Principi fondamentali:**
- ✅ Mai modificare main/master direttamente
- ✅ Ogni modifica su branch dedicato
- ✅ Ogni esecuzione produce log e report
- ✅ Nessun segreto nel codice
- ✅ Output sempre verificabile

## 📦 Installazione

### Prerequisiti

- Python 3.11+
- Git installato e configurato

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

### Verifica installazione

```powershell
# Verifica CLI
orchestrator --version

# Mostra configurazione
orchestrator config
```

## 🚀 Utilizzo

### Comando principale: `run`

Esegue un'orchestrazione completa su un repository target.

```powershell
orchestrator run --repo <path-al-repo> --goal "<obiettivo>"
```

**Esempio:**

```powershell
orchestrator run --repo C:\projects\my-software --goal "Aggiungi una healthcheck endpoint e test basilari"
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
│       └── core/
│           ├── config.py          # Configurazione
│           ├── run_context.py     # Stato della run
│           ├── git_ops.py         # Operazioni Git sicure
│           ├── planner.py         # Goal → Task list
│           ├── executor.py        # Coordinatore principale
│           └── roles/
│               ├── base.py        # Interfaccia base ruolo
│               ├── architect.py   # Analisi e design
│               ├── implementer.py # Modifiche codice
│               ├── tester.py      # Test e validazione
│               └── documenter.py  # Documentazione
├── tests/                         # Test pytest
├── templates/                     # Template per report
├── runs/                          # Artefatti delle run (ignorato da git)
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

Variabili d'ambiente supportate:

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
