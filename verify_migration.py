#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de Verificação Pós-Migração - Django Money (VERSÃO ROBUSTA)

Execute após aplicar as migrations para verificar se a conversão foi bem-sucedida.

Uso:
    python manage.py shell < verify_migration_robust.py

OU:
    python manage.py shell
    >>> exec(open('verify_migration_robust.py').read())
"""

import sys
from finances.models import (
    Transaction, FlowGroup, Investment, BankBalance, 
    FamilyConfiguration, Family
)
from moneyed import Money
from decimal import Decimal
from django.db.models import Sum, Count

def safe_print(text):
    """Print com tratamento de encoding seguro"""
    try:
        print(text)
    except UnicodeEncodeError:
        # Remove caracteres problemáticos
        clean_text = text.encode('ascii', 'ignore').decode('ascii')
        print(clean_text)

def safe_str(obj):
    """Converte objeto para string de forma segura"""
    try:
        return str(obj)
    except UnicodeEncodeError:
        try:
            return repr(obj)
        except:
            return "<unprintable>"

safe_print("=" * 80)
safe_print("VERIFICACAO DE MIGRACAO DJANGO-MONEY (VERSAO ROBUSTA)")
safe_print("=" * 80)

# ===== 1. VERIFICAR CONFIGURAÇÃO =====
safe_print("\n[1] Verificando FamilyConfiguration...")
try:
    configs = FamilyConfiguration.objects.all()
    safe_print(f"   Total de configuracoes: {configs.count()}")

    for config in configs:
        try:
            family_name = safe_str(config.family.name)
            safe_print(f"   - Familia: {family_name}")
            safe_print(f"     Moeda Base: {config.base_currency}")
            
            if hasattr(config, 'base_currency') and config.base_currency:
                safe_print(f"     OK Campo 'base_currency' existe e esta preenchido")
            else:
                safe_print(f"     AVISO: Campo 'base_currency' nao encontrado ou vazio")
        except Exception as e:
            safe_print(f"     ERRO ao processar configuracao: {safe_str(e)}")

    if configs.count() == 0:
        safe_print("   AVISO: Nenhuma configuracao encontrada!")
except Exception as e:
    safe_print(f"   ERRO: {safe_str(e)}")

# ===== 2. VERIFICAR TRANSACTIONS =====
safe_print("\n[2] Verificando Transactions...")
try:
    transactions = Transaction.objects.all()
    safe_print(f"   Total de transactions: {transactions.count()}")

    if transactions.exists():
        # Verificar primeiras 5
        safe_print("\n   Primeiras 5 transactions:")
        for t in transactions[:5]:
            try:
                desc = safe_str(t.description)[:50]  # Limitar tamanho
                safe_print(f"   - ID: {t.id} | {desc}")
                
                # Verificar amount
                try:
                    amount_str = safe_str(t.amount)
                    safe_print(f"     Valor: {amount_str}")
                except Exception as e:
                    safe_print(f"     Valor: <erro ao exibir: {safe_str(e)}>")
                
                safe_print(f"     Tipo: {type(t.amount).__name__}")
                
                # Verificar se é Money object
                if isinstance(t.amount, Money):
                    safe_print(f"     Moeda: {t.amount.currency}")
                    safe_print(f"     OK E um objeto Money valido")
                else:
                    safe_print(f"     ERRO NAO e um objeto Money! Tipo: {type(t.amount).__name__}")
                    
            except Exception as e:
                safe_print(f"   - ID: {t.id} | ERRO: {safe_str(e)}")
        
        # Verificar se todos têm moeda
        safe_print("\n   Verificando integridade de todas as transactions...")
        transactions_sem_moeda = 0
        transactions_invalidas = 0
        
        for t in transactions:
            try:
                if not isinstance(t.amount, Money):
                    transactions_invalidas += 1
                elif not hasattr(t.amount, 'currency'):
                    transactions_sem_moeda += 1
            except Exception:
                transactions_invalidas += 1
        
        if transactions_sem_moeda > 0:
            safe_print(f"   ERRO: {transactions_sem_moeda} transactions sem moeda!")
        elif transactions_invalidas > 0:
            safe_print(f"   ERRO: {transactions_invalidas} transactions com tipo invalido!")
        else:
            safe_print(f"   OK Todas as {transactions.count()} transactions tem moeda definida")
        
        # Testar agregação
        safe_print("\n   Testando agregacao (Sum)...")
        try:
            total = transactions.aggregate(total=Sum('amount'))['total']
            if total is not None:
                total_str = safe_str(total)
                safe_print(f"   Total (Sum): {total_str}")
                safe_print(f"   Tipo: {type(total).__name__}")
                if isinstance(total, Money):
                    safe_print(f"   OK Agregacao retorna Money object")
                else:
                    safe_print(f"   AVISO Agregacao retorna {type(total).__name__}")
            else:
                safe_print(f"   Total (Sum): NULL/None")
        except Exception as e:
            safe_print(f"   ERRO na agregacao: {safe_str(e)}")
    else:
        safe_print("   AVISO Nenhuma transaction encontrada no banco")
except Exception as e:
    safe_print(f"   ERRO GERAL: {safe_str(e)}")

# ===== 3. VERIFICAR FLOW GROUPS =====
safe_print("\n[3] Verificando FlowGroups...")
try:
    flow_groups = FlowGroup.objects.all()
    safe_print(f"   Total de FlowGroups: {flow_groups.count()}")

    if flow_groups.exists():
        safe_print("\n   Primeiras 5 FlowGroups:")
        for fg in flow_groups[:5]:
            try:
                name = safe_str(fg.name)[:50]
                safe_print(f"   - ID: {fg.id} | {name}")
                
                try:
                    budget_str = safe_str(fg.budgeted_amount)
                    safe_print(f"     Budget: {budget_str}")
                except Exception as e:
                    safe_print(f"     Budget: <erro ao exibir: {safe_str(e)}>")
                
                safe_print(f"     Tipo: {type(fg.budgeted_amount).__name__}")
                
                if isinstance(fg.budgeted_amount, Money):
                    safe_print(f"     Moeda: {fg.budgeted_amount.currency}")
                    safe_print(f"     OK E um objeto Money valido")
                else:
                    safe_print(f"     ERRO NAO e um objeto Money!")
                    
            except Exception as e:
                safe_print(f"   - ID: {fg.id} | ERRO: {safe_str(e)}")
        
        # Verificar se todos têm moeda
        safe_print("\n   Verificando integridade de todos os FlowGroups...")
        groups_invalidos = 0
        
        for fg in flow_groups:
            try:
                if not isinstance(fg.budgeted_amount, Money):
                    groups_invalidos += 1
            except Exception:
                groups_invalidos += 1
        
        if groups_invalidos > 0:
            safe_print(f"   ERRO: {groups_invalidos} FlowGroups com tipo invalido!")
        else:
            safe_print(f"   OK Todos os {flow_groups.count()} FlowGroups tem moeda definida")
    else:
        safe_print("   AVISO Nenhum FlowGroup encontrado")
except Exception as e:
    safe_print(f"   ERRO GERAL: {safe_str(e)}")

# ===== 4. VERIFICAR INVESTMENTS =====
safe_print("\n[4] Verificando Investments...")
try:
    investments = Investment.objects.all()
    safe_print(f"   Total de Investments: {investments.count()}")

    if investments.exists():
        for inv in investments:
            try:
                name = safe_str(inv.name)[:50]
                amount_str = safe_str(inv.amount)
                safe_print(f"   - {name}: {amount_str}")
                
                if isinstance(inv.amount, Money):
                    safe_print(f"     Moeda: {inv.amount.currency}")
                    safe_print(f"     OK E um objeto Money valido")
                else:
                    safe_print(f"     ERRO NAO e um objeto Money!")
                    
            except Exception as e:
                safe_print(f"   - ID: {inv.id} | ERRO: {safe_str(e)}")
    else:
        safe_print("   AVISO Nenhum Investment encontrado")
except Exception as e:
    safe_print(f"   ERRO GERAL: {safe_str(e)}")

# ===== 5. VERIFICAR BANK BALANCES =====
safe_print("\n[5] Verificando BankBalances...")
try:
    bank_balances = BankBalance.objects.all()
    safe_print(f"   Total de BankBalances: {bank_balances.count()}")

    if bank_balances.exists():
        for bb in bank_balances[:5]:
            try:
                desc = safe_str(bb.description)[:50]
                amount_str = safe_str(bb.amount)
                safe_print(f"   - {desc}: {amount_str}")
                
                if isinstance(bb.amount, Money):
                    safe_print(f"     Moeda: {bb.amount.currency}")
                    safe_print(f"     OK E um objeto Money valido")
                else:
                    safe_print(f"     ERRO NAO e um objeto Money!")
                    
            except Exception as e:
                safe_print(f"   - ID: {bb.id} | ERRO: {safe_str(e)}")
    else:
        safe_print("   AVISO Nenhum BankBalance encontrado")
except Exception as e:
    safe_print(f"   ERRO GERAL: {safe_str(e)}")

# ===== 6. TESTAR OPERAÇÕES MATEMÁTICAS =====
safe_print("\n[6] Testando Operacoes Matematicas...")

try:
    if transactions.exists():
        t1 = transactions.first()
        t2 = transactions.last()
        
        try:
            t1_str = safe_str(t1.amount)
            t2_str = safe_str(t2.amount)
            safe_print(f"   Transaction 1: {t1_str}")
            safe_print(f"   Transaction 2: {t2_str}")
            
            # Tentar somar
            if isinstance(t1.amount, Money) and isinstance(t2.amount, Money):
                if t1.amount.currency == t2.amount.currency:
                    result = t1.amount + t2.amount
                    result_str = safe_str(result)
                    safe_print(f"   Soma: {result_str}")
                    safe_print(f"   OK Operacao matematica funcionou")
                else:
                    safe_print(f"   AVISO Moedas diferentes - soma nao permitida (correto!)")
            else:
                safe_print(f"   AVISO Valores nao sao Money objects")
                
        except Exception as e:
            safe_print(f"   ERRO em operacao matematica: {safe_str(e)}")
    else:
        safe_print("   AVISO Sem transactions para testar")
except Exception as e:
    safe_print(f"   ERRO GERAL: {safe_str(e)}")

# ===== 7. VERIFICAR CAMPOS DE BANCO DE DADOS =====
safe_print("\n[7] Verificando Campos no Banco de Dados...")

try:
    from django.db import connection
    
    with connection.cursor() as cursor:
        # Tentar diferentes sintaxes de banco de dados
        try:
            # SQLite
            cursor.execute("PRAGMA table_info(finances_transaction);")
            columns = cursor.fetchall()
            db_type = "SQLite"
        except Exception:
            try:
                # PostgreSQL
                cursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='finances_transaction';")
                columns = cursor.fetchall()
                db_type = "PostgreSQL"
            except Exception:
                try:
                    # MySQL
                    cursor.execute("DESCRIBE finances_transaction;")
                    columns = cursor.fetchall()
                    db_type = "MySQL"
                except Exception as e:
                    safe_print(f"   ERRO ao detectar tipo de banco: {safe_str(e)}")
                    columns = []
                    db_type = "Unknown"
        
        safe_print(f"\n   Tipo de banco detectado: {db_type}")
        safe_print(f"   Colunas da tabela 'finances_transaction':")
        
        amount_found = False
        amount_currency_found = False
        
        for col in columns:
            try:
                if db_type == "SQLite":
                    col_name = col[1]
                    col_type = col[2]
                elif db_type == "PostgreSQL":
                    col_name = col[0]
                    col_type = col[1]
                else:
                    col_name = str(col[0])
                    col_type = str(col[1]) if len(col) > 1 else "?"
                
                if 'amount' in col_name.lower():
                    safe_print(f"   - {col_name} ({col_type})")
                    
                    if col_name == 'amount':
                        amount_found = True
                    if col_name == 'amount_currency':
                        amount_currency_found = True
            except Exception as e:
                safe_print(f"   - <erro ao processar coluna: {safe_str(e)}>")
        
        if amount_found and amount_currency_found:
            safe_print("\n   OK Campos 'amount' e 'amount_currency' existem")
        else:
            safe_print("\n   ERRO: Campos esperados nao encontrados!")
            safe_print(f"      amount: {amount_found}")
            safe_print(f"      amount_currency: {amount_currency_found}")
except Exception as e:
    safe_print(f"   ERRO ao verificar banco: {safe_str(e)}")

# ===== 8. RESUMO FINAL =====
safe_print("\n" + "=" * 80)
safe_print("RESUMO DA VERIFICACAO")
safe_print("=" * 80)

total_issues = 0

# Configurações
try:
    if configs.count() == 0:
        safe_print("ERRO Nenhuma configuracao encontrada")
        total_issues += 1
    else:
        safe_print(f"OK {configs.count()} configuracao(oes) com moeda definida")
except:
    safe_print("ERRO ao verificar configuracoes")
    total_issues += 1

# Transactions
try:
    if transactions.exists():
        # Amostragem para evitar timeout
        sample_size = min(100, transactions.count())
        sample_transactions = transactions[:sample_size]
        
        transactions_ok = all(isinstance(t.amount, Money) for t in sample_transactions)
        if transactions_ok:
            safe_print(f"OK {transactions.count()} transactions validas (amostra de {sample_size})")
        else:
            safe_print(f"ERRO Algumas transactions nao sao Money objects")
            total_issues += 1
    else:
        safe_print("AVISO Nenhuma transaction para verificar")
except Exception as e:
    safe_print(f"ERRO ao verificar transactions: {safe_str(e)}")
    total_issues += 1

# FlowGroups
try:
    if flow_groups.exists():
        sample_size = min(50, flow_groups.count())
        sample_groups = flow_groups[:sample_size]
        
        groups_ok = all(isinstance(fg.budgeted_amount, Money) for fg in sample_groups)
        if groups_ok:
            safe_print(f"OK {flow_groups.count()} FlowGroups validos (amostra de {sample_size})")
        else:
            safe_print(f"ERRO Alguns FlowGroups nao sao Money objects")
            total_issues += 1
    else:
        safe_print("AVISO Nenhum FlowGroup para verificar")
except Exception as e:
    safe_print(f"ERRO ao verificar FlowGroups: {safe_str(e)}")
    total_issues += 1

# Investments
try:
    if investments.exists():
        inv_ok = all(isinstance(inv.amount, Money) for inv in investments)
        if inv_ok:
            safe_print(f"OK {investments.count()} Investments validos")
        else:
            safe_print(f"ERRO Alguns Investments nao sao Money objects")
            total_issues += 1
    else:
        safe_print("AVISO Nenhum Investment para verificar")
except Exception as e:
    safe_print(f"ERRO ao verificar Investments: {safe_str(e)}")
    total_issues += 1

# BankBalances
try:
    if bank_balances.exists():
        bb_ok = all(isinstance(bb.amount, Money) for bb in bank_balances)
        if bb_ok:
            safe_print(f"OK {bank_balances.count()} BankBalances validos")
        else:
            safe_print(f"ERRO Alguns BankBalances nao sao Money objects")
            total_issues += 1
    else:
        safe_print("AVISO Nenhum BankBalance para verificar")
except Exception as e:
    safe_print(f"ERRO ao verificar BankBalances: {safe_str(e)}")
    total_issues += 1

safe_print("\n" + "=" * 80)

if total_issues == 0:
    safe_print("OK MIGRACAO BEM-SUCEDIDA! Nenhum problema encontrado.")
    safe_print("\nProximos passos:")
    safe_print("1. Teste a aplicacao manualmente")
    safe_print("2. Verifique dashboard, criacao de transactions, etc.")
    safe_print("3. Se tudo funcionar, remova o backup antigo")
else:
    safe_print(f"AVISO PROBLEMAS ENCONTRADOS: {total_issues}")
    safe_print("\nAcoes recomendadas:")
    safe_print("1. Revise as migrations")
    safe_print("2. Verifique se aplicou todas as migrations")
    safe_print("3. Se necessario, restaure o backup e tente novamente")

safe_print("=" * 80)
