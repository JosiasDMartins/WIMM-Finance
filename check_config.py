#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de diagnostico para verificar configuracoes do SweetMoney
Execute: docker exec sweetmoney python check_config.py
"""

import os
import sys

def check_file_exists(path):
    """Verifica se um arquivo existe e mostra suas permissoes"""
    if os.path.exists(path):
        stat_info = os.stat(path)
        size = stat_info.st_size
        print(f"[OK] Arquivo existe: {path}")
        print(f"  - Tamanho: {size} bytes")
        print(f"  - Permissoes: {oct(stat_info.st_mode)[-3:]}")
        return True
    else:
        print(f"[ERRO] Arquivo NAO existe: {path}")
        return False

def read_local_settings(path):
    """Le e mostra configuracoes importantes do local_settings.py"""
    try:
        print(f"\n[INFO] Lendo {path}...")
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Simula o exec() para capturar as variaveis
        # Use globals dict with 'os' imported to match Django settings behavior
        local_vars = {'os': __import__('os')}
        exec(content, local_vars)

        print("\n[INFO] Configuracoes encontradas:")

        if 'SECRET_KEY' in local_vars:
            print(f"  SECRET_KEY: {'*' * 20} (definido, {len(local_vars['SECRET_KEY'])} caracteres)")
        else:
            print("  SECRET_KEY: [ERRO] NAO DEFINIDO")

        if 'DEBUG' in local_vars:
            print(f"  DEBUG: {local_vars['DEBUG']}")
        else:
            print("  DEBUG: [ERRO] NAO DEFINIDO")

        if 'ALLOWED_HOSTS' in local_vars:
            print(f"  ALLOWED_HOSTS: {local_vars['ALLOWED_HOSTS']}")
        else:
            print("  ALLOWED_HOSTS: [ERRO] NAO DEFINIDO")

        if 'CSRF_TRUSTED_ORIGINS' in local_vars:
            print(f"  CSRF_TRUSTED_ORIGINS: {local_vars.get('CSRF_TRUSTED_ORIGINS', [])}")
        else:
            print("  CSRF_TRUSTED_ORIGINS: [ERRO] NAO DEFINIDO")

        if 'DATABASES' in local_vars:
            db = local_vars['DATABASES'].get('default', {})
            engine = db.get('ENGINE', 'Not set')
            if 'postgresql' in engine:
                print(f"  DATABASES: PostgreSQL")
                print(f"    - HOST: {db.get('HOST', 'Not set')}")
                print(f"    - NAME: {db.get('NAME', 'Not set')}")
                print(f"    - USER: {db.get('USER', 'Not set')}")
            elif 'sqlite' in engine:
                print(f"  DATABASES: SQLite")
                print(f"    - NAME: {db.get('NAME', 'Not set')}")
            else:
                print(f"  DATABASES: {engine}")
        else:
            print("  DATABASES: [ERRO] NAO DEFINIDO")

        return True

    except Exception as e:
        print(f"\n[ERRO] Erro ao ler arquivo: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_django_settings():
    """Verifica as configuracoes finais do Django"""
    try:
        print("\n[INFO] Verificando configuracoes Django carregadas...")
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wimm_project.settings')

        from django.conf import settings

        print(f"  DEBUG: {settings.DEBUG}")
        print(f"  ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
        print(f"  CSRF_TRUSTED_ORIGINS: {getattr(settings, 'CSRF_TRUSTED_ORIGINS', [])}")

        db_engine = settings.DATABASES['default']['ENGINE']
        print(f"  DATABASE ENGINE: {db_engine}")

        return True

    except Exception as e:
        print(f"\n[ERRO] Erro ao carregar Django settings: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 70)
    print("SweetMoney - Diagnostico de Configuracao")
    print("=" * 70)

    # Verifica ambiente
    print("\n[INFO] Ambiente:")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  Working directory: {os.getcwd()}")

    # Verifica local_settings.py
    print("\n[INFO] Verificando arquivos de configuracao:")

    external_path = '/app/config/local_settings.py'
    local_path = 'config/local_settings.py'

    exists_external = check_file_exists(external_path)
    exists_local = check_file_exists(local_path)

    # Tenta ler o arquivo
    if exists_external:
        read_local_settings(external_path)
    elif exists_local:
        read_local_settings(local_path)
    else:
        print("\n[AVISO] NENHUM local_settings.py encontrado!")
        print("        O sistema usara configuracoes padrao (SQLite + DEBUG=False)")

    # Verifica variaveis de ambiente
    print("\n[INFO] Variaveis de ambiente relevantes:")
    env_vars = [
        'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_HOST', 'POSTGRES_PORT',
        'REDIS_HOST', 'REDIS_PORT',
        'AUTO_MIGRATE', 'AUTO_COLLECTSTATIC'
    ]
    for var in env_vars:
        value = os.environ.get(var, 'Not set')
        if 'PASSWORD' in var:
            value = '***' if value != 'Not set' else 'Not set'
        print(f"  {var}: {value}")

    # Verifica Django settings finais
    check_django_settings()

    print("\n" + "=" * 70)
    print("[OK] Diagnostico concluido")
    print("=" * 70)

if __name__ == '__main__':
    main()
