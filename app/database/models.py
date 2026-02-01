from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    join_date = Column(DateTime, default=datetime.utcnow)
    balance = Column(Float, default=0.0)
    
    # Связи
    subscription = relationship("Subscription", back_populates="user", uselist=False)
    v2ray_keys = relationship("V2RayKey", back_populates="user")
    payments = relationship("Payment", back_populates="user")

class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    tariff_id = Column(Integer, ForeignKey("tariffs.id"))
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    
    # Связи
    user = relationship("User", back_populates="subscription")
    tariff = relationship("Tariff")

class Tariff(Base):
    __tablename__ = "tariffs"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    price_rub = Column(Float, nullable=False)
    duration_days = Column(Integer, nullable=False)
    description = Column(String(500))
    is_active = Column(Boolean, default=True)

class V2RayKey(Base):
    __tablename__ = "v2ray_keys"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    key_type = Column(String(20), default="vmess")
    uuid = Column(String(36))
    server_address = Column(String(100))
    server_port = Column(Integer)
    config_json = Column(Text)
    key_string = Column(Text, nullable=False)
    qr_code_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    last_used = Column(DateTime)
    
    # Связи
    user = relationship("User", back_populates="v2ray_keys")

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    invoice_id = Column(Integer, unique=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="USDT")
    status = Column(String(20), default="pending")
    payment_method = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime)
    
    # Связи
    user = relationship("User", back_populates="payments")