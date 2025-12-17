"""
Currency utility functions for managing period currencies.

This module handles currency-related operations including:
- Getting period currency
- Ensuring period exists with correct currency
"""

import logging
from ..models import Period

logger = logging.getLogger(__name__)


def get_period_currency(family, period_start_date):
    """
    Retorna a moeda para um período específico.
    Consulta primeiro a tabela Period. Se não existir entrada, usa base_currency da família.
    """
    period = Period.objects.filter(
        family=family,
        start_date=period_start_date
    ).first()

    if period:
        return period.currency

    # Se não existe período registrado, usa moeda padrão da família
    config = getattr(family, 'configuration', None)
    if config:
        return config.base_currency

    return 'USD'  # Fallback padrão


def ensure_period_exists(family, start_date, end_date, period_type):
    """
    Garante que existe uma entrada de Period para o período especificado.
    Se não existir, cria uma nova com a moeda padrão da família.

    Returns: Period object
    """
    period, created = Period.objects.get_or_create(
        family=family,
        start_date=start_date,
        defaults={
            'end_date': end_date,
            'period_type': period_type,
            'currency': family.configuration.base_currency if hasattr(family, 'configuration') else 'USD'
        }
    )

    # Se já existe mas precisa atualizar end_date ou period_type
    if not created:
        updated = False
        if period.end_date != end_date:
            period.end_date = end_date
            updated = True
        if period.period_type != period_type:
            period.period_type = period_type
            updated = True
        if updated:
            period.save()

    return period
