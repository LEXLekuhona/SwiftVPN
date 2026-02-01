"""
Сервисы проекта
"""
from app.services.vpn import V2RayService, VPSService, X3UIService
from app.services.payment import StarsService
from app.services.user import SubscriptionService
from app.services.database import Database, db

__all__ = [
    'V2RayService',
    'VPSService',
    'X3UIService',
    'StarsService',
    'SubscriptionService',
    'Database',
    'db'
]
