import uuid
import json
import base64
from io import BytesIO
from datetime import datetime, timedelta
from typing import Dict, Optional
from loguru import logger

class V2RayGenerator:
    """Генератор ключей для V2RayTun (поддерживает VMess и VLESS)"""
    
    @staticmethod
    def generate_vless_config(server_config: Dict, user_uuid: str = None) -> tuple[str, str]:
        """Генерация конфигурации VLESS
        
        Returns:
            tuple: (vless_url, user_uuid)
        """
        if not user_uuid:
            user_uuid = str(uuid.uuid4())
        
        # Определяем параметры
        network = server_config.get("network", "tcp")
        path = server_config.get("path", "")
        tls_enabled = server_config.get("tls", False)
        security = server_config.get("security", "none")  # none, tls, reality
        flow = server_config.get("flow", "")  # для xtls-rprx-vision
        sni = server_config.get("sni", server_config.get("address", ""))
        host = server_config.get("address", "")
        port = server_config["port"]
        remark = server_config.get("location", "VPN Server")
        
        # Формируем параметры для VLESS URL
        params = []
        
        # Encryption (обычно none для VLESS)
        params.append("encryption=none")
        
        # Security
        if security == "tls":
            params.append("security=tls")
            if sni:
                params.append(f"sni={sni}")
        elif security == "reality":
            params.append("security=reality")
            # Server Name (SNI) для Reality - обязательный параметр
            server_name = server_config.get("server_name", server_config.get("sni", ""))
            if server_name:
                params.append(f"sni={server_name}")
            else:
                logger.warning(f"⚠️ server_name отсутствует для Reality! Ключ может быть неполным.")
            # Fingerprint для Reality - опциональный параметр (если не указан, используется значение по умолчанию)
            fingerprint = server_config.get("fingerprint", "")
            if fingerprint:
                params.append(f"fp={fingerprint}")
            else:
                # Fingerprint опционален - если не указан, клиент использует значение по умолчанию
                logger.debug(f"ℹ️ fingerprint не указан для Reality, будет использовано значение по умолчанию")
            # Public Key (pbk) для Reality - обязательный параметр
            public_key = server_config.get("reality_pbk", server_config.get("pbk", ""))
            if public_key:
                params.append(f"pbk={public_key}")
            else:
                logger.error(f"❌ reality_pbk отсутствует для Reality! Ключ будет неполным и не будет работать!")
                logger.error(f"   Убедитесь, что reality_pbk указан в VPN_SERVERS в .env или извлекается из inbound")
            # Short ID (sid) для Reality - обязательный параметр
            # Если указано несколько Short ID через запятую, берем только первый
            short_id = server_config.get("reality_sid", server_config.get("sid", ""))
            if short_id:
                # Берем только первый Short ID, если указано несколько через запятую
                short_id = short_id.split(",")[0].strip()
                params.append(f"sid={short_id}")
            else:
                logger.error(f"❌ reality_sid отсутствует для Reality! Ключ будет неполным и не будет работать!")
            # SpiderX для обхода блокировок (добавляем только если указан)
            spiderx = server_config.get("spiderx", "")
            if spiderx and spiderx.strip():  # Добавляем только если не пустой
                params.append(f"spx={spiderx}")
        else:
            params.append("security=none")
        
        # Flow (для xtls-rprx-vision)
        if flow:
            params.append(f"flow={flow}")
        
        # Network type
        params.append(f"type={network}")
        
        # Header type
        if network == "tcp":
            params.append("headerType=none")
        elif network == "ws":
            params.append("headerType=none")
            if path:
                params.append(f"path={path}")
            if sni:
                params.append(f"host={sni}")
        
        # Формируем VLESS URL
        query_string = "&".join(params)
        vless_url = f"vless://{user_uuid}@{host}:{port}?{query_string}#{remark}"
        
        # ВАЖНО: Логируем параметры для отладки
        if security == "reality":
            logger.debug(f"🔍 Параметры Reality в ключе:")
            logger.debug(f"   - security: {security}")
            logger.debug(f"   - server_name: {server_config.get('server_name', 'N/A')}")
            logger.debug(f"   - fingerprint: {server_config.get('fingerprint', 'N/A')}")
            logger.debug(f"   - reality_pbk: {'присутствует' if server_config.get('reality_pbk') else 'ОТСУТСТВУЕТ'}")
            logger.debug(f"   - reality_sid: {server_config.get('reality_sid', 'N/A')}")
            logger.debug(f"   - spiderx: {server_config.get('spiderx', 'N/A')}")
            logger.debug(f"   - Параметры в URL: {query_string}")
            if not server_config.get('reality_pbk'):
                logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: reality_pbk отсутствует! Ключ будет неполным!")
        
        return vless_url, user_uuid
    
    @staticmethod
    def generate_vmess_config(server_config: Dict, user_uuid: str = None) -> tuple[str, str]:
        """Генерация конфигурации VMess
        
        Returns:
            tuple: (vmess_url, user_uuid)
        """
        if not user_uuid:
            user_uuid = str(uuid.uuid4())
        
        # Определяем сетевой протокол (ws для WebSocket или tcp)
        network = server_config.get("network", "tcp")
        path = server_config.get("path", "")
        tls_enabled = server_config.get("tls", False)
        sni = server_config.get("sni", server_config.get("address", ""))
        
        v2ray_config = {
            "v": "2",
            "ps": f"VPN {server_config.get('location', 'Server')}",
            "add": server_config["address"],
            "port": server_config["port"],
            "id": user_uuid,
            "aid": 0,
            "scy": "auto",
            "net": network,
            "type": "none" if network == "tcp" else "",
            "host": sni if network == "ws" else "",
            "path": path if network == "ws" else "",
            "tls": "tls" if tls_enabled else "",
            "sni": sni if tls_enabled else "",
            "alpn": "",
            "fp": ""
        }
        
        config_str = json.dumps(v2ray_config)
        config_base64 = base64.b64encode(config_str.encode()).decode()
        return f"vmess://{config_base64}", user_uuid
    
    @staticmethod
    def generate_config(server_config: Dict, user_uuid: str = None) -> tuple[str, str]:
        """Генерация конфигурации (VMess или VLESS) в зависимости от типа сервера
        
        Returns:
            tuple: (key_url, user_uuid)
        """
        # Определяем тип протокола
        protocol = server_config.get("type", "vmess").lower()
        
        # Логируем для отладки
        from loguru import logger
        logger.debug(f"generate_config: protocol={protocol}, security={server_config.get('security', 'N/A')}")
        
        if protocol == "vless":
            key, uuid = V2RayGenerator.generate_vless_config(server_config, user_uuid)
            logger.debug(f"Сгенерирован VLESS ключ: длина={len(key)}, начало={key[:30]}...")
            return key, uuid
        else:
            key, uuid = V2RayGenerator.generate_vmess_config(server_config, user_uuid)
            logger.debug(f"Сгенерирован VMess ключ: длина={len(key)}, начало={key[:30]}...")
            return key, uuid
    
    @staticmethod
    def generate_qr_code(data: str) -> str:
        """Генерация QR-кода в base64"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()

class V2RayService:
    def __init__(self, db):
        self.db = db
        self.generator = V2RayGenerator()
        self._vps_service = None  # Кэш для VPSService
        self._inbound_cache = None  # Кэш для inbound
        self._inbound_cache_time = None  # Время кэширования
    
    async def _get_vps_service(self):
        """Получение VPSService с кэшированием"""
        if self._vps_service is None:
            from app.services.vpn import VPSService
            self._vps_service = VPSService()
        return self._vps_service

    async def _get_db_user_id(self, telegram_user_id: int) -> Optional[int]:
        async with self.db.session_maker() as session:
            from sqlalchemy import select
            from app.database.models import User

            stmt = select(User.id).where(User.telegram_id == telegram_user_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def _get_subscription_end_date(self, telegram_user_id: int):
        """Дата окончания активной подписки."""
        async with self.db.session_maker() as session:
            from sqlalchemy import select, and_
            from app.database.models import Subscription, User

            stmt = (
                select(Subscription.end_date)
                .join(User)
                .where(
                    and_(
                        User.telegram_id == telegram_user_id,
                        Subscription.is_active == True,
                    )
                )
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    @staticmethod
    def _datetime_to_expiry_ms(dt: datetime) -> int:
        return int(dt.timestamp() * 1000)

    async def sync_subscription_to_x3ui(self, telegram_user_id: int) -> bool:
        """Синхронизирует срок подписки из БД бота с клиентом в 3x-ui."""
        end_date = await self._get_subscription_end_date(telegram_user_id)
        if not end_date:
            logger.warning(f"Нет активной подписки для sync: user_id={telegram_user_id}")
            return False

        key_data = await self.get_active_key(telegram_user_id)
        if not key_data or not key_data.get("uuid"):
            logger.info(
                f"Нет активного ключа для sync в 3x-ui: user_id={telegram_user_id}"
            )
            return False

        expiry_ms = self._datetime_to_expiry_ms(end_date)
        vps_service = await self._get_vps_service()
        success = await vps_service.update_user_expiry(key_data["uuid"], expiry_ms)

        if success:
            db_user_id = await self._get_db_user_id(telegram_user_id)
            async with self.db.session_maker() as session:
                from sqlalchemy import select, or_, update
                from app.database.models import V2RayKey

                conditions = [V2RayKey.user_id == telegram_user_id]
                if db_user_id:
                    conditions.append(V2RayKey.user_id == db_user_id)

                stmt = (
                    update(V2RayKey)
                    .where(V2RayKey.uuid == key_data["uuid"], V2RayKey.is_active == True)
                    .values(expires_at=end_date)
                )
                await session.execute(stmt)
                await session.commit()
            logger.info(
                f"✅ Срок подписки синхронизирован в 3x-ui: user_id={telegram_user_id}, "
                f"до {end_date.strftime('%d.%m.%Y')}"
            )
        return success
    
    async def _get_inbound_cached(self, force_refresh: bool = False):
        """Получение inbound с кэшированием (кэш на 60 секунд)"""
        import time
        current_time = time.time()
        
        # Проверяем кэш (действителен 60 секунд)
        if not force_refresh and self._inbound_cache and self._inbound_cache_time:
            if current_time - self._inbound_cache_time < 60:
                logger.debug("✅ Используем кэшированный inbound")
                return self._inbound_cache
        
        # Получаем свежий inbound
        try:
            vps_service = await self._get_vps_service()
            if hasattr(vps_service, 'x3ui_service') and vps_service.x3ui_service:
                inbound = await vps_service.x3ui_service.get_inbound()
                if inbound:
                    self._inbound_cache = inbound
                    self._inbound_cache_time = current_time
                    logger.debug("✅ Inbound закэширован")
                    return inbound
        except Exception as e:
            logger.warning(f"⚠️ Не удалось получить inbound: {e}")
        
        return None
    
    async def _extract_reality_params_from_inbound(self, inbound: Dict, server_config: Dict):
        """Извлечение параметров Reality из inbound и добавление в server_config"""
        try:
            stream_settings = inbound.get("streamSettings", {})
            if isinstance(stream_settings, str):
                try:
                    stream_settings = json.loads(stream_settings)
                except:
                    logger.warning(f"⚠️ Не удалось распарсить streamSettings как JSON")
                    stream_settings = {}
            
            if stream_settings:
                security = stream_settings.get("security", "")
                if security == "reality":
                    server_config["security"] = "reality"
                    logger.info(f"✅ Добавлен security=reality в server_config")
                    
                    reality_settings = stream_settings.get("realitySettings", {})
                    if reality_settings:
                        # Извлекаем serverNames (используем первый)
                        server_names = reality_settings.get("serverNames", [])
                        if server_names:
                            server_config["server_name"] = server_names[0]
                            logger.info(f"✅ Добавлен server_name={server_config['server_name']} в server_config")
                        
                        # Извлекаем fingerprint (опциональный параметр)
                        fingerprint = reality_settings.get("fingerprint", "")
                        if fingerprint:
                            server_config["fingerprint"] = fingerprint
                            logger.info(f"✅ Добавлен fingerprint={fingerprint} в server_config")
                        else:
                            # Fingerprint опционален - если отсутствует, клиент использует значение по умолчанию
                            logger.debug(f"ℹ️ fingerprint отсутствует в inbound, будет использовано значение по умолчанию")
                        
                        # Извлекаем shortIds (используем первый)
                        short_ids = reality_settings.get("shortIds", [])
                        if short_ids:
                            server_config["reality_sid"] = short_ids[0]
                            logger.info(f"✅ Добавлен reality_sid={server_config['reality_sid']} в server_config")
                        
                        # Извлекаем publicKey (если есть)
                        # ВАЖНО: На сервере в 3x-ui используется privateKey, а для клиента нужен publicKey
                        # publicKey обычно должен быть указан в .env или вычисляться отдельно
                        public_key = reality_settings.get("publicKey", "")
                        private_key = reality_settings.get("privateKey", "")
                        mldsa65_seed = reality_settings.get("mldsa65Seed", "")
                        
                        # Если publicKey есть в inbound, используем его (приоритет)
                        if public_key:
                            server_config["reality_pbk"] = public_key
                            logger.info(f"✅ Добавлен reality_pbk из publicKey в inbound")
                        # Если publicKey нет в inbound, но есть в исходном server_config, сохраняем его
                        elif server_config.get("reality_pbk"):
                            logger.info(f"✅ Используем reality_pbk из исходного server_config (VPN_SERVERS в .env)")
                        # Если и там нет, но есть privateKey, предупреждаем
                        elif private_key:
                            logger.warning(f"⚠️ publicKey отсутствует в inbound и server_config, но есть privateKey. Для клиента нужен publicKey!")
                            logger.warning(f"⚠️ Убедитесь, что reality_pbk указан в VPN_SERVERS в .env")
                        
                        # Извлекаем spiderX
                        spider_x = reality_settings.get("spiderX", "")
                        if spider_x:
                            server_config["spiderx"] = spider_x
                            logger.info(f"✅ Добавлен spiderx={spider_x} в server_config")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при извлечении параметров Reality из inbound: {e}")
    
    async def create_key(self, user_id: int, server_config: Dict) -> Dict:
        """Создание ключа для пользователя"""
        # Генерируем UUID для пользователя
        user_uuid = str(uuid.uuid4())
        
        # ВАЖНО: Если type не указан в server_config, определяем его автоматически
        # Если есть параметры Reality, то это VLESS
        if "type" not in server_config or not server_config.get("type"):
            logger.warning(f"⚠️ Тип протокола не указан в server_config! Определяем автоматически...")
            if server_config.get("security") == "reality" or server_config.get("reality_pbk") or server_config.get("reality_sid"):
                server_config["type"] = "vless"
                logger.info(f"✅ Автоматически определен тип протокола: vless (по параметрам Reality)")
                # ВАЖНО: Если security не установлен, но есть reality_pbk, нужно извлечь параметры из inbound
                if not server_config.get("security") or server_config.get("security") != "reality":
                    logger.info(f"⚠️ security не установлен, извлекаем параметры Reality из inbound...")
                    inbound = await self._get_inbound_cached()
                    if inbound:
                        await self._extract_reality_params_from_inbound(inbound, server_config)
            else:
                # Пробуем определить из 3x-ui API
                try:
                    inbound = await self._get_inbound_cached()
                    if inbound and inbound.get("protocol"):
                        server_config["type"] = inbound.get("protocol").lower()
                        logger.info(f"✅ Автоматически определен тип протокола из 3x-ui: {server_config['type']}")
                        
                        # ВАЖНО: Извлекаем параметры Reality из inbound и добавляем в server_config
                        await self._extract_reality_params_from_inbound(inbound, server_config)
                    else:
                        server_config["type"] = "vless"
                        logger.warning(f"⚠️ Не удалось определить тип из 3x-ui, используем vless по умолчанию")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось определить тип протокола из 3x-ui: {e}")
                    # Используем значение по умолчанию
                    server_config["type"] = "vless"  # По умолчанию vless, так как в 3x-ui используется vless
                    logger.info(f"✅ Используем vless по умолчанию")
        
        # ВАЖНО: Если type уже установлен, но параметры Reality отсутствуют, извлекаем их из inbound
        if server_config.get("type") == "vless" and (not server_config.get("security") or server_config.get("security") != "reality"):
            if server_config.get("reality_pbk") or server_config.get("reality_sid"):
                # Есть параметры Reality, но security не установлен - извлекаем из inbound
                logger.info(f"⚠️ security не установлен, но есть параметры Reality, извлекаем из inbound...")
                inbound = await self._get_inbound_cached()
                if inbound:
                    await self._extract_reality_params_from_inbound(inbound, server_config)
        
        # ВАЖНО: Логируем параметры перед генерацией
        protocol_type = server_config.get("type", "vmess").lower()
        logger.info(f"🔑 Генерация ключа для user_id={user_id}:")
        logger.info(f"   - protocol_type из server_config: {protocol_type}")
        logger.info(f"   - security: {server_config.get('security', 'N/A')}")
        logger.info(f"   - reality_pbk: {server_config.get('reality_pbk', 'N/A')[:20] if server_config.get('reality_pbk') else 'N/A'}...")
        logger.info(f"   - reality_sid: {server_config.get('reality_sid', 'N/A')}")
        
        # Определяем тип протокола из конфигурации сервера
        key_string, generated_uuid = self.generator.generate_config(server_config, user_uuid)
        
        # ВАЖНО: Проверяем, что ключ правильного типа
        logger.info(f"✅ Сгенерированный ключ: длина={len(key_string)} символов")
        logger.info(f"   - Начало: {key_string[:50]}...")
        logger.info(f"   - Конец: ...{key_string[-50:]}")
        if protocol_type == "vless" and not key_string.startswith("vless://"):
            logger.error(f"❌ ОШИБКА: Ожидался vless://, но получен: {key_string[:30]}...")
        elif protocol_type == "vmess" and not key_string.startswith("vmess://"):
            logger.error(f"❌ ОШИБКА: Ожидался vmess://, но получен: {key_string[:30]}...")
        
        subscription_end = await self._get_subscription_end_date(user_id)
        expires_at = subscription_end or (datetime.utcnow() + timedelta(days=30))
        expiry_time_ms = self._datetime_to_expiry_ms(expires_at)
        db_user_id = await self._get_db_user_id(user_id)
        storage_user_id = db_user_id or user_id

        async with self.db.session_maker() as session:
            from sqlalchemy import text
            from app.database.models import V2RayKey

            deactivate_conditions = ["user_id = :telegram_id"]
            params = {"telegram_id": user_id}
            if db_user_id:
                deactivate_conditions.append("user_id = :db_user_id")
                params["db_user_id"] = db_user_id

            await session.execute(
                text(
                    f"UPDATE v2ray_keys SET is_active = false WHERE {' OR '.join(deactivate_conditions)}"
                ),
                params,
            )
            
            # Определяем тип протокола
            protocol_type = server_config.get("type", "vmess").lower()
            
            # ВАЖНО: Логируем перед сохранением
            logger.info(f"💾 Сохранение ключа в базу данных:")
            logger.info(f"   - key_type: {protocol_type}")
            logger.info(f"   - key_string длина: {len(key_string)} символов")
            logger.info(f"   - key_string начинается с: {key_string[:20]}...")
            
            # Сохраняем полную конфигурацию сервера
            config_data = {
                "type": protocol_type,
                "network": server_config.get("network", "tcp"),
                "path": server_config.get("path", ""),
                "tls": server_config.get("tls", False),
                "security": server_config.get("security", "none"),
                "flow": server_config.get("flow", ""),
                "sni": server_config.get("sni", server_config.get("address", "")),
                "server_name": server_config.get("server_name", ""),  # Для Reality
                "fingerprint": server_config.get("fingerprint", ""),  # Для Reality
                "reality_pbk": server_config.get("reality_pbk", server_config.get("pbk", "")),  # Public Key для Reality
                "reality_sid": server_config.get("reality_sid", server_config.get("sid", "")),  # Short ID для Reality
                "spiderx": server_config.get("spiderx", "")  # Для Reality
            }
            
            # ВАЖНО: Логируем перед сохранением
            logger.info(f"💾 Сохранение ключа в базу данных:")
            logger.info(f"   - key_type: {protocol_type}")
            logger.info(f"   - key_string длина: {len(key_string)} символов")
            logger.info(f"   - key_string начинается с: {key_string[:20]}...")
            logger.info(f"   - key_string заканчивается на: ...{key_string[-20:]}")
            
            # Создаем новый ключ
            v2ray_key = V2RayKey(
                user_id=storage_user_id,
                key_type=protocol_type,  # vmess или vless
                uuid=generated_uuid,  # Сохраняем UUID для управления на сервере
                server_address=server_config["address"],
                server_port=server_config["port"],
                config_json=json.dumps(config_data),
                key_string=key_string,
                qr_code_url=None,  # QR-код не используется
                is_active=True,
                expires_at=expires_at,
                last_used=datetime.utcnow()
            )
            
            session.add(v2ray_key)
            await session.commit()
            
            logger.info(
                f"✅ Создан ключ для user_id={user_id}, uuid={generated_uuid}, "
                f"server={server_config['address']}:{server_config['port']}"
            )
            
            # Автоматически добавляем пользователя на VPS через 3x-ui API или SSH
            try:
                vps_service = await self._get_vps_service()
                
                # Используем уникальный email на основе UUID, чтобы избежать дубликатов
                unique_email = f"user_{generated_uuid[:8]}"
                # Передаем тип протокола и порт для правильного поиска inbound
                success, config = await vps_service.add_user_to_v2ray(
                    generated_uuid,
                    unique_email,
                    protocol_type,
                    server_config.get("port", 443),
                    expiry_time_ms=expiry_time_ms,
                )
                if success:
                    logger.info(f"✅ Пользователь {generated_uuid} автоматически добавлен на VPS")
                    if config:
                        logger.info(f"✅ Получена конфигурация Xray через API: {len(config.get('inbounds', []))} inbounds")
                        logger.debug(f"Конфигурация Xray: {json.dumps(config, indent=2)[:500]}...")  # Логируем первые 500 символов
                        
                        # Обновляем config_json в базе данных с полной конфигурацией Xray
                        try:
                            v2ray_key.config_json = json.dumps(config)
                            await session.commit()
                            logger.info(f"✅ Полная конфигурация Xray сохранена в базу данных для user_id={user_id}")
                        except Exception as e:
                            logger.error(f"Ошибка сохранения конфигурации в базу данных: {e}")
                else:
                    logger.warning(f"⚠️ Не удалось автоматически добавить пользователя {generated_uuid} на VPS. Добавьте вручную.")
            except Exception as e:
                logger.error(f"Ошибка автоматического добавления на VPS: {e}")
                import traceback
                logger.error(traceback.format_exc())
                logger.warning(f"⚠️ Добавьте пользователя {generated_uuid} на VPS вручную")
            
            return {
                "key": key_string,
                "expires_at": expires_at,
                "server": server_config,
                "uuid": generated_uuid
            }
    
    async def get_active_key(self, user_id: int) -> Optional[Dict]:
        """Получение активного ключа пользователя (user_id — telegram_id)."""
        async with self.db.session_maker() as session:
            from sqlalchemy import select, or_
            from app.database.models import User, V2RayKey

            db_user_id_stmt = select(User.id).where(User.telegram_id == user_id)
            db_user_id = (await session.execute(db_user_id_stmt)).scalar_one_or_none()

            conditions = [V2RayKey.user_id == user_id]
            if db_user_id:
                conditions.append(V2RayKey.user_id == db_user_id)

            stmt = (
                select(V2RayKey)
                .where(V2RayKey.is_active == True, or_(*conditions))
                .limit(1)
            )
            
            result = await session.execute(stmt)
            key = result.scalar_one_or_none()
            
            if key:
                # Обновляем время последнего использования
                key.last_used = datetime.utcnow()
                await session.commit()
                
                # Восстанавливаем конфигурацию сервера из config_json
                server_config = {}
                
                # Получаем location из settings.VPN_SERVERS по адресу и порту
                location = "Сервер"  # Значение по умолчанию
                from config.settings import settings
                if settings.VPN_SERVERS:
                    for server in settings.VPN_SERVERS:
                        if server.get("address") == key.server_address and server.get("port") == key.server_port:
                            location = server.get("location", "Сервер")
                            break
                
                if key.config_json:
                    try:
                        config_data = json.loads(key.config_json)
                        # ВАЖНО: Используем type из config_data, если он есть, иначе из key.key_type
                        protocol_type = config_data.get("type") or key.key_type or "vless"
                        server_config = {
                            "address": key.server_address,
                            "port": key.server_port,
                            "location": location,
                            "type": protocol_type,  # ВАЖНО: Правильный тип протокола
                            "network": config_data.get("network", "tcp"),
                            "path": config_data.get("path", ""),
                            "tls": config_data.get("tls", False),
                            "security": config_data.get("security", "none"),
                            "flow": config_data.get("flow", ""),
                            "sni": config_data.get("sni", ""),
                            "server_name": config_data.get("server_name", ""),  # Для Reality
                            "fingerprint": config_data.get("fingerprint", ""),  # Для Reality
                            "reality_pbk": config_data.get("reality_pbk", ""),  # Public Key для Reality
                            "reality_sid": config_data.get("reality_sid", ""),  # Short ID для Reality
                            "spiderx": config_data.get("spiderx", "")  # Для Reality
                        }
                        logger.debug(f"Восстановлен server_config из config_json: type={protocol_type}, security={server_config.get('security')}")
                    except Exception as e:
                        logger.warning(f"Ошибка парсинга config_json: {e}, используем key.key_type")
                        protocol_type = key.key_type or "vless"
                        server_config = {
                            "address": key.server_address,
                            "port": key.server_port,
                            "location": location,
                            "type": protocol_type
                        }
                else:
                    # Если config_json отсутствует, используем key_type из базы
                    protocol_type = key.key_type or "vless"
                    server_config = {
                        "address": key.server_address,
                        "port": key.server_port,
                        "location": location,
                        "type": protocol_type
                    }
                    logger.warning(f"config_json отсутствует, используем key_type={protocol_type} из базы")
                
                # Возвращаем ключ напрямую из базы данных (быстро, без регенерации)
                # Регенерация нужна только при создании нового ключа или изменении конфигурации
                return {
                    "key": key.key_string,
                    "expires_at": key.expires_at,
                    "created_at": key.created_at,
                    "uuid": key.uuid,
                    "server": server_config
                }
            
            return None