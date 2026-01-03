# Sistema de Backup e Restauração - Implementação Completa

## Resumo

Este documento descreve a implementação completa do sistema de backup e restauração para o projeto WIMM-Finance, incluindo suporte para SQLite e PostgreSQL com migração automática entre os tipos de banco de dados.

## Data de Implementação

2025-12-20

## Arquivos Criados

### 1. `finances/utils/db_type_detector.py`
**Função**: Detectar automaticamente o tipo de arquivo de backup (SQLite ou PostgreSQL)

**Funcionalidades**:
- Tenta abrir arquivo como SQLite database
- Verifica assinatura de arquivo PostgreSQL dump (PGDMP)
- Identifica dumps SQL plain text
- Retorna: 'sqlite', 'postgresql', ou 'unknown'

**Uso**:
```python
from finances.utils.db_type_detector import detect_backup_type
backup_type = detect_backup_type('/path/to/backup.file')
```

---

### 2. `finances/utils/db_restore_migration.py`
**Função**: Migrar dados de backup SQLite para banco PostgreSQL ativo

**Funcionalidades**:
- Salva arquivo SQLite enviado em local temporário
- Valida integridade do SQLite (PRAGMA integrity_check)
- Cria backup de segurança do PostgreSQL atual
- Dropa todos os dados do PostgreSQL (transacional)
- Exporta dados do SQLite usando `dumpdata`
- Importa dados no PostgreSQL usando `loaddata`
- Reseta sequences do PostgreSQL
- Verifica migração completa

**Processo**:
1. Validação do arquivo SQLite
2. Leitura de metadata (family, users)
3. Backup automático do PostgreSQL atual
4. Drop de todas as tabelas PostgreSQL
5. Recriação do schema com migrations
6. Exportação de dados do SQLite (JSON)
7. Importação de dados no PostgreSQL
8. Reset de sequences
9. Verificação final

**Uso**:
```python
from finances.utils.db_restore_migration import restore_sqlite_to_postgres
result = restore_sqlite_to_postgres(uploaded_file)
```

---

## Arquivos Modificados

### 1. `finances/utils/db_restore_postgres.py`
**Modificação**: Adicionado backup de segurança antes da restauração

**Mudanças**:
- STEP 3 adicionado: Cria backup automático do PostgreSQL antes de restaurar
- Usa `create_database_backup()` para criar backup de segurança
- Continua mesmo se backup falhar (warning, não fatal)

**Código Adicionado** (linhas 81-97):
```python
# STEP 3: Create backup of current PostgreSQL database before restore
logger.info(f"[PG_RESTORE] Creating backup of current PostgreSQL database")
backup_created = False
try:
    from finances.utils.db_backup import create_database_backup
    backup_result = create_database_backup()

    if backup_result['success']:
        backup_created = True
        logger.info(f"[PG_RESTORE] PostgreSQL backup created: {backup_result['filename']}")
    else:
        logger.warning(f"[PG_RESTORE] Could not create PostgreSQL backup: {backup_result.get('error')}")
except Exception as backup_error:
    logger.warning(f"[PG_RESTORE] Could not create PostgreSQL backup: {backup_error}")
```

---

### 2. `finances/views/views_updater.py`
**Modificação**: Implementação completa de todos os cenários de restauração

**Função `restore_backup()` reescrita completamente** (linhas 575-767)

**Cenários Implementados**:

#### **Cenário 1: PostgreSQL → SQLite (BLOQUEADO)**
- Detecta tentativa de restaurar backup PostgreSQL em sistema SQLite
- Retorna erro claro explicando que operação não é suportada
- Sugere usar backup SQLite

**Código**:
```python
if backup_file_type == 'postgresql' and current_db_type == 'sqlite':
    return JsonResponse({
        'success': False,
        'error': _('Cannot restore PostgreSQL backup to SQLite database'),
        'details': _('Your system is currently running with SQLite database...')
    }, status=400)
```

#### **Cenário 2: SQLite → PostgreSQL (MIGRAÇÃO COM CONFIRMAÇÃO)**
- Primeira tentativa: Retorna resposta solicitando confirmação de migração
- Frontend mostra modal explicando que migração será feita
- Segunda tentativa (com confirmação): Executa migração usando `restore_sqlite_to_postgres()`

**Fluxo**:
1. Usuário envia arquivo SQLite
2. Backend detecta que sistema é PostgreSQL
3. Backend retorna `needs_migration_confirmation: true`
4. Frontend mostra modal detalhado sobre migração
5. Usuário confirma
6. Frontend reenvia com `confirm_migration=true`
7. Backend executa migração completa

**Código**:
```python
elif backup_file_type == 'sqlite' and current_db_type == 'postgresql':
    if not migration_confirmed:
        return JsonResponse({
            'success': False,
            'needs_migration_confirmation': True,
            'message': _('The backup file is from SQLite...')
        }, status=200)
    else:
        from finances.utils.db_restore_migration import restore_sqlite_to_postgres
        result = restore_sqlite_to_postgres(backup_file_for_migration)
```

#### **Cenário 3: SQLite → SQLite (RESTAURAÇÃO TRANSACIONAL)**
- Usa função existente `restore_database_from_file()`
- Processo transacional já implementado
- Backup de segurança automático (pre_restore_*)

**Código**:
```python
elif backup_file_type == 'sqlite' and current_db_type == 'sqlite':
    from finances.utils.db_restore import restore_database_from_file
    result = restore_database_from_file(backup_file_for_restore)
```

#### **Cenário 4: PostgreSQL → PostgreSQL (RESTAURAÇÃO TRANSACIONAL)**
- Usa função modificada `restore_postgres_database_from_file()`
- Agora cria backup de segurança antes de restaurar
- Usa `pg_restore --clean --if-exists`

**Código**:
```python
elif backup_file_type == 'postgresql' and current_db_type == 'postgresql':
    from finances.utils.db_restore_postgres import restore_postgres_database_from_file
    result = restore_postgres_database_from_file(backup_file_for_restore)
```

**Fluxo Geral da View**:
```
1. Validar upload
2. Detectar tipo de DB atual (sqlite/postgresql)
3. Salvar arquivo em temp
4. Detectar tipo de backup (sqlite/postgresql/unknown)
5. Verificar se migração é necessária
6. Executar cenário apropriado:
   - PGSQL→SQLITE: Bloquear com erro
   - SQLITE→PGSQL: Pedir confirmação, depois migrar
   - SQLITE→SQLITE: Restaurar transacional
   - PGSQL→PGSQL: Restaurar transacional (com backup)
7. Limpar arquivo temporário
8. Deletar cookie de sessão (logout)
9. Retornar resultado
```

---

### 3. `finances/templates/finances/configurations.html`
**Modificação**: Frontend completo para suportar todos os cenários

**Mudanças**:

#### **HTML** (linha 480):
- Atualizado `accept` do input para aceitar `.sqlite3` e `.dump`
- Texto alterado para "SQLite (.sqlite3) or PostgreSQL (.dump) files"

**Antes**:
```html
<input type="file" id="restore-file-input" accept=".sqlite3" class="hidden">
<p class="text-xs text-gray-500">{% trans "SQLite3 database files only" %}</p>
```

**Depois**:
```html
<input type="file" id="restore-file-input" accept=".sqlite3,.dump" class="hidden">
<p class="text-xs text-gray-500">{% trans "SQLite (.sqlite3) or PostgreSQL (.dump) files" %}</p>
```

#### **JavaScript** (linhas 749-901):
Função `btnRestore.addEventListener()` completamente reescrita

**Novos Fluxos**:

**STEP 1: Aviso inicial com recomendação de backup**
```javascript
const backupWarning = await GenericModal.confirm(
    "WARNING: Restoring a backup will replace ALL current data...\n\n" +
    "IMPORTANT: It is strongly recommended to create a backup...\n\n" +
    "Do you want to continue?",
    "Confirm Database Restore"
);
```

**STEP 2: Primeira tentativa de restore**
- Envia arquivo sem `confirm_migration`
- Backend detecta tipo e verifica se migração é necessária

**STEP 3: Handler para confirmação de migração (se necessário)**
```javascript
if (data.needs_migration_confirmation) {
    const migrationConfirmed = await GenericModal.confirm(
        "MIGRATION REQUIRED\n\n" +
        data.message + "\n\n" +
        "The following will happen:\n" +
        "• Current PostgreSQL database will be backed up\n" +
        "• All current PostgreSQL data will be dropped\n" +
        "• SQLite data will be migrated to PostgreSQL\n\n" +
        "Do you want to proceed?",
        "Confirm Migration"
    );

    if (migrationConfirmed) {
        // Reenvia com confirm_migration=true
        formData2.append('confirm_migration', 'true');
        // ... segunda tentativa
    }
}
```

**STEP 4: Handler para restore normal (sem migração)**
```javascript
if (data.success) {
    // Mostra preview
    familyName.textContent = data.family.name;
    data.users.forEach(user => {
        const li = document.createElement('li');
        li.textContent = `${user.username} (${user.role})`;
        usersList.appendChild(li);
    });

    // Sucesso e redirect
    await GenericModal.alert(
        "Database restored successfully! Redirecting...",
        "Restore Successful"
    );
    window.location.href = '/login/';
}
```

**Tratamento de Erros Detalhado**:
```javascript
} else {
    let errorMessage = data.error;
    if (data.details) {
        errorMessage += '\n\nDetails: ' + data.details;
    }
    GenericModal.alert(errorMessage, "Restore Failed");
}
```

---

## Fluxos Completos de Cada Cenário

### Cenário 1: SQLite → SQLite

```
┌─────────────────┐
│ User: Upload    │
│ backup.sqlite3  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ Frontend: Mostra confirmação inicial        │
│ "WARNING: Will replace all data"            │
│ "IMPORTANT: Create backup first"            │
└────────┬────────────────────────────────────┘
         │ Confirm
         ▼
┌─────────────────────────────────────────────┐
│ Backend: POST /restore-backup/              │
│ - Detecta: current_db = 'sqlite'            │
│ - Detecta: backup_type = 'sqlite'           │
│ - Cenário 3: SQLite → SQLite                │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ db_restore.py: restore_database_from_file() │
│ 1. Criar lock file                          │
│ 2. Fechar conexões Django                   │
│ 3. Validar integridade (PRAGMA)             │
│ 4. Ler metadata (family, users)             │
│ 5. Criar backup segurança (pre_restore_*)   │
│ 6. Limpar DB atual (DROP + VACUUM)          │
│ 7. Restaurar usando SQLite backup API       │
│ 8. Verificar integridade do restaurado      │
│ 9. Forçar Django reconnect                  │
│ 10. Criar reload flag                       │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ Frontend: Mostra preview + success          │
│ "Database restored successfully!"           │
│ Redirect para /login/                       │
└─────────────────────────────────────────────┘
```

---

### Cenário 2: SQLite → PostgreSQL (MIGRAÇÃO)

```
┌─────────────────┐
│ User: Upload    │
│ backup.sqlite3  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ Frontend: Mostra confirmação inicial        │
│ "WARNING: Will replace all data"            │
└────────┬────────────────────────────────────┘
         │ Confirm
         ▼
┌─────────────────────────────────────────────┐
│ Backend: POST /restore-backup/ (tentativa 1)│
│ - Detecta: current_db = 'postgresql'        │
│ - Detecta: backup_type = 'sqlite'           │
│ - Cenário 2: SQLite → PostgreSQL            │
│ - migration_confirmed = False               │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ Backend: Retorna                            │
│ {                                           │
│   success: false,                           │
│   needs_migration_confirmation: true,       │
│   message: "Migration required..."          │
│ }                                           │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ Frontend: Mostra modal de migração          │
│ "MIGRATION REQUIRED"                        │
│ "• PostgreSQL will be backed up"            │
│ "• All PostgreSQL data will be dropped"     │
│ "• SQLite data will be migrated"            │
└────────┬────────────────────────────────────┘
         │ Confirm Migration
         ▼
┌─────────────────────────────────────────────┐
│ Frontend: POST /restore-backup/ (tentativa 2)│
│ - formData.append('confirm_migration',true) │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ Backend: Detecta migration_confirmed = true │
│ Executa: restore_sqlite_to_postgres()       │
└────────┬────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│ db_restore_migration.py:                     │
│ restore_sqlite_to_postgres()                 │
│ 1. Salvar SQLite temp                        │
│ 2. Validar integridade SQLite                │
│ 3. Ler metadata (family, users)              │
│ 4. Criar backup do PostgreSQL atual          │
│ 5. Fechar conexões Django                    │
│ 6. Adicionar conexão temp 'sqlite_migration' │
│ 7. Exportar dados: dumpdata → JSON           │
│ 8. Remover conexão temp                      │
│ 9. Drop todas tabelas PostgreSQL (CASCADE)   │
│ 10. Rodar migrations (recriar schema)        │
│ 11. Importar dados: loaddata ← JSON          │
│ 12. Reset sequences PostgreSQL               │
│ 13. Verificar migração                       │
│ 14. Criar reload flag                        │
└────────┬─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ Frontend: Mostra success                    │
│ "Database migrated from SQLite to PGSQL!"   │
│ Redirect para /login/                       │
└─────────────────────────────────────────────┘
```

---

### Cenário 3: PostgreSQL → PostgreSQL

```
┌─────────────────┐
│ User: Upload    │
│ backup.dump     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ Frontend: Mostra confirmação inicial        │
│ "WARNING: Will replace all data"            │
└────────┬────────────────────────────────────┘
         │ Confirm
         ▼
┌─────────────────────────────────────────────┐
│ Backend: POST /restore-backup/              │
│ - Detecta: current_db = 'postgresql'        │
│ - Detecta: backup_type = 'postgresql'       │
│ - Cenário 4: PostgreSQL → PostgreSQL        │
└────────┬────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│ db_restore_postgres.py:                      │
│ restore_postgres_database_from_file()        │
│ 1. Validar arquivo                           │
│ 2. Salvar em temp                            │
│ 3. NOVO: Criar backup do PostgreSQL atual    │
│ 4. Fechar conexões Django                    │
│ 5. Executar pg_restore:                      │
│    --clean --if-exists --no-owner --no-acl   │
│ 6. Forçar Django reconnect                   │
│ 7. Verificar DB restaurado (ler family/users)│
│ 8. Criar reload flag                         │
└────────┬─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ Frontend: Mostra preview + success          │
│ "Database restored successfully!"           │
│ Redirect para /login/                       │
└─────────────────────────────────────────────┘
```

---

### Cenário 4: PostgreSQL → SQLite (BLOQUEADO)

```
┌─────────────────┐
│ User: Upload    │
│ backup.dump     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ Frontend: Mostra confirmação inicial        │
│ "WARNING: Will replace all data"            │
└────────┬────────────────────────────────────┘
         │ Confirm
         ▼
┌─────────────────────────────────────────────┐
│ Backend: POST /restore-backup/              │
│ - Detecta: current_db = 'sqlite'            │
│ - Detecta: backup_type = 'postgresql'       │
│ - Cenário 1: PostgreSQL → SQLite            │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ Backend: Retorna erro HTTP 400              │
│ {                                           │
│   success: false,                           │
│   error: "Cannot restore PostgreSQL...",    │
│   details: "Your system is SQLite..."       │
│ }                                           │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ Frontend: Mostra erro detalhado             │
│ "Cannot restore PostgreSQL backup to        │
│  SQLite database"                           │
│ "Details: Your system is currently..."      │
└─────────────────────────────────────────────┘
```

---

## Recursos Implementados

### ✅ Detecção Automática de Tipo de DB Ativo
- Função `get_database_engine()` em `db_backup.py`
- Retorna 'sqlite' ou 'postgresql'

### ✅ Detecção Automática de Tipo de Arquivo de Backup
- Novo: `detect_backup_type()` em `db_type_detector.py`
- Tenta abrir como SQLite
- Verifica assinatura PGDMP
- Retorna 'sqlite', 'postgresql', ou 'unknown'

### ✅ Backup Transacional por Tipo
- **SQLite**: SQLite Backup API (transacional, seguro)
- **PostgreSQL**: `pg_dump -Fc` (custom format, comprimido)

### ✅ Restauração SQLite → SQLite
- Processo em 11 passos (já existia)
- Lock file para WebSocket
- Backup de segurança (pre_restore_*)
- Wipe usando DROP + VACUUM (não deleta arquivo)
- Restauração usando SQLite Backup API
- Verificação de integridade

### ✅ Restauração SQLite → PostgreSQL (NOVO)
- Migração completa usando dumpdata/loaddata
- Backup automático do PostgreSQL antes de migrar
- Confirmação obrigatória via modal
- Drop transacional de dados PostgreSQL
- Reset de sequences
- Verificação completa

### ✅ Restauração PostgreSQL → PostgreSQL
- `pg_restore --clean --if-exists`
- **NOVO**: Backup automático antes de restaurar
- Timeout de 10 minutos
- Verificação pós-restore

### ✅ Validação PostgreSQL → SQLite
- Bloqueio com mensagem clara
- Explica por que não é suportado
- Sugere usar backup SQLite

### ✅ Confirmações com Modal Genérico
- Aviso inicial sobre perda de dados
- Recomendação para criar backup antes de restaurar
- Modal específico para migração SQLite→PostgreSQL
- Mensagens de sucesso/erro detalhadas

### ✅ Backup de Segurança Automático
- SQLite: Cria `pre_restore_TIMESTAMP.sqlite3`
- PostgreSQL: Cria backup antes de restaurar (NOVO)
- Permite rollback em caso de erro

### ✅ Limpeza Transacional
- SQLite: DROP all tables + VACUUM (não deleta arquivo)
- PostgreSQL: DROP all tables CASCADE

### ✅ Mensagens de Erro Detalhadas
- Frontend mostra `error` e `details` separadamente
- Logs completos no backend para debugging
- Tratamento específico para cada tipo de erro

---

## Casos de Uso

### 1. Backup Regular (Admin)
```
1. Admin acessa Settings → Backup & Restore
2. Clica em "Download Database Backup"
3. Sistema detecta tipo de DB (SQLite ou PostgreSQL)
4. Cria backup apropriado
5. Download automático do arquivo
```

### 2. Restauração Simples (Mesmo tipo de DB)
```
1. Admin acessa Settings → Backup & Restore
2. Seleciona arquivo backup (.sqlite3 ou .dump)
3. Clica "Restore Database"
4. Modal: "WARNING: Will replace all data. Create backup first?"
5. Confirma
6. Sistema detecta tipos (backup e atual)
7. Restaura transacionalmente
8. Mostra preview (family, users)
9. Redirect para login
```

### 3. Migração SQLite → PostgreSQL
```
1. Sistema muda de SQLite para PostgreSQL (settings.py)
2. Admin quer restaurar backup antigo (.sqlite3)
3. Seleciona backup.sqlite3
4. Clica "Restore Database"
5. Modal 1: "WARNING: Will replace all data..."
6. Confirma
7. Backend detecta migração necessária
8. Modal 2: "MIGRATION REQUIRED. PostgreSQL will be backed up..."
9. Confirma migração
10. Sistema:
    - Cria backup do PostgreSQL atual
    - Dropa dados PostgreSQL
    - Migra dados do SQLite
    - Reset sequences
11. Mostra preview + success
12. Redirect para login
```

### 4. Tentativa PostgreSQL → SQLite (Bloqueada)
```
1. Sistema rodando com SQLite
2. Admin tenta restaurar backup.dump (PostgreSQL)
3. Seleciona arquivo
4. Clica "Restore Database"
5. Modal: "WARNING: Will replace all data..."
6. Confirma
7. Backend detecta incompatibilidade
8. Retorna erro detalhado
9. Frontend mostra:
   "Cannot restore PostgreSQL backup to SQLite database"
   "Details: Your system is currently running with SQLite..."
```

---

## Segurança e Confiabilidade

### Validações Implementadas
- ✅ DEMO_MODE: Bloqueia backup/restore em modo demo
- ✅ Validação de upload: Arquivo presente
- ✅ Validação de tipo: Arquivo é SQLite ou PostgreSQL válido
- ✅ Integridade SQLite: `PRAGMA integrity_check`
- ✅ Integridade PostgreSQL: Verifica se Django pode ler após restore
- ✅ Validação de compatibilidade: Bloqueia PostgreSQL→SQLite

### Backups de Segurança
- ✅ SQLite: `pre_restore_TIMESTAMP.sqlite3`
- ✅ PostgreSQL: Backup automático antes de restore/migração
- ✅ Rollback automático em caso de erro

### Transacionalidade
- ✅ SQLite: Usa SQLite Backup API (transacional)
- ✅ PostgreSQL: `pg_restore --clean` (transacional)
- ✅ Lock file para prevenir conexões WebSocket durante restore

### Logs Detalhados
- ✅ Todos os processos logam no formato `[MODULE] message`
- ✅ Log de cada step do processo
- ✅ Logs de erro com stack trace
- ✅ Logs de verificação e validação

---

## Compatibilidade

### Tipos de Banco Suportados
- ✅ SQLite 3.x
- ✅ PostgreSQL 12+ (requer `pg_dump` e `pg_restore` instalados)

### Formatos de Backup Suportados
- ✅ SQLite: `.sqlite3` (arquivo database completo)
- ✅ PostgreSQL: `.dump` (custom format via pg_dump -Fc)
- ✅ PostgreSQL: Plain SQL dumps (detectado mas pode requerer ajustes)

### Cenários de Migração
- ✅ SQLite → SQLite (restauração)
- ✅ SQLite → PostgreSQL (migração)
- ✅ PostgreSQL → PostgreSQL (restauração)
- ❌ PostgreSQL → SQLite (bloqueado)

---

## Testes Recomendados

### Testes Básicos
1. **Backup SQLite**: Criar backup, verificar arquivo gerado
2. **Backup PostgreSQL**: Criar backup, verificar arquivo .dump
3. **Restore SQLite→SQLite**: Restaurar backup válido
4. **Restore PostgreSQL→PostgreSQL**: Restaurar backup válido

### Testes de Migração
5. **Migração SQLite→PostgreSQL**:
   - Sistema com SQLite, restaurar backup SQLite em PostgreSQL
   - Verificar confirmação obrigatória
   - Verificar backup do PostgreSQL foi criado
   - Verificar dados migrados corretamente
   - Verificar sequences resetadas

### Testes de Validação
6. **Arquivo corrompido SQLite**: Deve falhar com erro de integridade
7. **Arquivo corrompido PostgreSQL**: Deve falhar com erro do pg_restore
8. **Arquivo tipo errado**: Deve retornar 'unknown' e bloquear
9. **PostgreSQL→SQLite**: Deve bloquear com mensagem clara

### Testes de UI
10. **Modal de confirmação inicial**: Verificar texto e botões
11. **Modal de migração**: Verificar aparece apenas quando necessário
12. **Preview de restore**: Verificar family e users aparecem
13. **Mensagens de erro**: Verificar error e details aparecem
14. **Redirect após sucesso**: Verificar vai para /login/

### Testes de Segurança
15. **DEMO_MODE**: Verificar backup/restore bloqueados
16. **Session cookie**: Verificar é deletado após restore
17. **Backup automático**: Verificar arquivo criado antes de restore
18. **Rollback**: Forçar erro durante restore, verificar rollback

---

## Limitações Conhecidas

### PostgreSQL→SQLite
- Não é possível migrar de PostgreSQL para SQLite
- Razão: PostgreSQL usa features não disponíveis no SQLite (sequences, types, etc)
- Solução: Manter backups SQLite antigos ou não fazer downgrade

### Plain SQL Dumps
- PostgreSQL plain SQL dumps são detectados mas podem requerer ajustes
- Recomendado usar sempre custom format (`pg_dump -Fc`)

### Timeout
- SQLite backup: Sem timeout (geralmente rápido)
- PostgreSQL backup: 5 minutos (pode ser insuficiente para DBs muito grandes)
- PostgreSQL restore: 10 minutos (pode ser insuficiente para DBs muito grandes)

### Migração de Dados Complexos
- Sequences PostgreSQL são resetadas após loaddata
- Pode haver incompatibilidades de tipos específicos
- Recomendado testar migração em ambiente de staging primeiro

---

## Próximos Passos (Melhorias Futuras)

### Sugestões de Melhorias
1. **Metadata extraction de PostgreSQL dumps**: Ler family/users antes de restaurar
2. **Compressão de backups SQLite**: Suportar .sqlite3.gz
3. **Backups agendados**: Celery task para backup automático diário/semanal
4. **Cloud storage**: Upload automático para S3/Google Cloud
5. **Point-in-time recovery**: Suportar restore de timestamp específico
6. **Restauração seletiva**: Escolher quais families/periods restaurar
7. **Validação de espaço em disco**: Verificar antes de criar backup
8. **Progress bar**: Mostrar progresso de restore/migração
9. **Audit trail**: Log de quem fez backup/restore e quando
10. **Email notifications**: Notificar admins após backup/restore

---

## Changelog

### 2025-12-20 - v1.0.0 (Implementação Inicial)

#### Adicionado
- ✅ Detecção automática de tipo de arquivo de backup
- ✅ Migração SQLite → PostgreSQL com confirmação
- ✅ Backup automático antes de restauração PostgreSQL
- ✅ Validação e bloqueio de PostgreSQL → SQLite
- ✅ Confirmações detalhadas com modal genérico
- ✅ Suporte para arquivos .sqlite3 e .dump no upload
- ✅ Mensagens de erro detalhadas (error + details)

#### Modificado
- ✅ View `restore_backup()` reescrita completamente
- ✅ Frontend configurations.html atualizado
- ✅ `db_restore_postgres.py` agora cria backup de segurança

#### Arquivos Criados
- ✅ `finances/utils/db_type_detector.py`
- ✅ `finances/utils/db_restore_migration.py`
- ✅ `BACKUP_RESTORE_IMPLEMENTATION.md` (este documento)

---

## Autores

Implementado por: Claude Sonnet 4.5 (Anthropic)
Data: 2025-12-20
Projeto: WIMM-Finance

---

## Contato para Dúvidas

Para dúvidas sobre esta implementação, consulte:
1. Este documento (BACKUP_RESTORE_IMPLEMENTATION.md)
2. Comentários no código (docstrings e inline comments)
3. Logs do sistema (formato `[MODULE] message`)
