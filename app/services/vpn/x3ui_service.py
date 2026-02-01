import aiohttp
import json
from typing import Optional, Dict, List
from loguru import logger
from config.settings import settings


class X3UIService:
    """Сервис для работы с 3x-ui API"""
    
    def __init__(self):
        api_url_full = getattr(settings, 'X3UI_API_URL', 'http://148.253.213.153:2053')
        
        # Извлекаем базовый URL и WebBasePath
        from urllib.parse import urlparse, urlunparse
        
        parsed = urlparse(api_url_full)
        # Базовый URL (scheme + netloc)
        self.base_url = urlunparse((parsed.scheme, parsed.netloc, '', '', '', ''))
        # WebBasePath (если указан в URL)
        self.web_base_path = parsed.path.rstrip('/') if parsed.path else ""
        
        self.username = getattr(settings, 'X3UI_USERNAME', 'admin')
        self.password = getattr(settings, 'X3UI_PASSWORD', 'admin')
        self.inbound_id = getattr(settings, 'X3UI_INBOUND_ID', 1)  # ID inbound в 3x-ui
        
        logger.info(f"3x-ui базовый URL: {self.base_url}, WebBasePath: {self.web_base_path}")
        
    async def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Optional[Dict]:
        """Выполнение запроса к API 3x-ui (использует сессию)"""
        try:
            # Создаем сессию для сохранения cookies
            # Отключаем проверку SSL (для самоподписанных сертификатов)
            import ssl
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(limit=10, ssl=ssl_context)
            timeout = aiohttp.ClientTimeout(total=60)  # Увеличено до 60 секунд
            
            # Создаем cookie jar для сохранения cookies
            cookie_jar = aiohttp.CookieJar()
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout, cookie_jar=cookie_jar) as session:
                # Заголовки для авторизации (минимальные)
                login_headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/plain, */*",
                }
                
                # Сначала логинимся (сессия сохранит cookies)
                login_data = {
                    "username": self.username,
                    "password": self.password
                }
                
                # В 3x-ui API пути могут различаться
                # WebBasePath добавляется к базовому пути
                # Правильный путь к авторизации: /login (найден через тестирование)
                # Путь к API endpoints: /panel/api/... (например, /panel/api/server/status)
                api_paths = [
                    "/login",  # Правильный путь к авторизации (найден через тестирование)
                    "/panel/api/login",  # Альтернативный вариант
                    "/xui/api/login",  # Альтернативный вариант
                    "/api/login"  # Без префикса
                ]
                
                login_url = None
                login_result = None
                session_cookie = None
                
                for api_path in api_paths:
                    if self.web_base_path:
                        test_url = f"{self.base_url}{self.web_base_path}{api_path}"
                    else:
                        test_url = f"{self.base_url}{api_path}"
                    
                    logger.info(f"🔐 Попытка авторизации в 3x-ui: {test_url}")
                    
                    async with session.post(
                        test_url,
                        json=login_data,
                        headers=login_headers
                    ) as test_response:
                        if test_response.status == 200:
                            try:
                                result = await test_response.json()
                                if result.get("success"):
                                    login_url = test_url
                                    login_result = result
                                    logger.info(f"✅ Авторизация успешна через: {test_url}")
                                    
                                    # Извлекаем cookie из Set-Cookie заголовка
                                    set_cookies = test_response.headers.getall('Set-Cookie', [])
                                    for set_cookie in set_cookies:
                                        if '3x-ui=' in set_cookie:
                                            # Извлекаем значение cookie
                                            # Формат: "3x-ui=value; Path=/; Expires=..."
                                            parts = set_cookie.split(';')
                                            for part in parts:
                                                part = part.strip()
                                                if part.startswith('3x-ui='):
                                                    cookie_value = part.split('=', 1)[1]  # Используем split с maxsplit=1 на случай, если в значении есть '='
                                                    session_cookie = f"lang=ru-RU; 3x-ui={cookie_value}"
                                                    logger.info(f"✅ Cookie извлечен: 3x-ui={cookie_value[:50]}...")
                                                    break
                                            if session_cookie:
                                                break
                                    if session_cookie:
                                        break
                            except:
                                pass
                        elif test_response.status not in [404, 301, 302]:
                            # Если не 404/редирект, значит путь правильный, но может быть ошибка авторизации
                            try:
                                text = await test_response.text()
                                logger.debug(f"Ответ от {test_url}: {test_response.status}, {text[:100]}")
                            except:
                                pass
                
                if not login_url or not login_result:
                    logger.error(f"Ошибка: не удалось найти рабочий API endpoint для авторизации")
                    logger.error("Попробованы пути: " + ", ".join([f"{self.base_url}{self.web_base_path if self.web_base_path else ''}{p}" for p in api_paths]))
                    return None
                
                if not session_cookie:
                    # Пробуем получить cookie из cookie jar
                    for cookie in session.cookie_jar:
                        if cookie.key == '3x-ui':
                            session_cookie = f"lang=ru-RU; 3x-ui={cookie.value}"
                            logger.info(f"✅ Cookie получен из jar: 3x-ui={cookie.value[:50]}...")
                            break
                
                # Если cookie не найден, но авторизация прошла успешно, 
                # возможно cookie не установился из-за параметров Set-Cookie
                # В этом случае используем cookie jar напрямую
                if not session_cookie:
                    logger.warning("⚠️ Cookie не извлечен, но авторизация прошла успешно")
                    logger.warning("Попробуем использовать cookie jar напрямую")
                
                # Теперь выполняем основной запрос (cookies сохранены в сессии)
                # API endpoints требуют WebBasePath в пути
                if endpoint.startswith("/"):
                    api_endpoint = endpoint
                else:
                    api_endpoint = f"/{endpoint}"
                
                if self.web_base_path:
                    url = f"{self.base_url}{self.web_base_path}{api_endpoint}"
                else:
                    url = f"{self.base_url}{api_endpoint}"
                
                # Заголовки, найденные через DevTools (из cURL команды)
                headers = {
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Connection": "keep-alive",
                    "Content-Type": "application/json",
                    "Referer": f"{self.base_url}{self.web_base_path}/panel/inbounds",
                    "Sec-Fetch-Dest": "empty",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Site": "same-origin",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
                    "X-Requested-With": "XMLHttpRequest",
                    "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"macOS"'
                }
                
                # Добавляем cookie в заголовки
                # Важно: cookie должен быть в заголовках, так как aiohttp не всегда сохраняет cookies из Set-Cookie
                if session_cookie:
                    headers["Cookie"] = session_cookie
                    logger.debug(f"Используем cookie в заголовках: {session_cookie[:50]}...")
                else:
                    # Пробуем получить cookie из jar как запасной вариант
                    cookies_in_jar = list(session.cookie_jar)
                    if cookies_in_jar:
                        cookie_str = "; ".join([f"{c.key}={c.value}" for c in cookies_in_jar])
                        headers["Cookie"] = cookie_str
                        logger.debug(f"Используем cookies из jar: {len(cookies_in_jar)} cookies")
                    else:
                        logger.warning("⚠️ Cookie не найден ни в заголовках, ни в jar")
                
                if method.upper() == "GET":
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            text = await response.text()
                            logger.error(f"Ошибка GET {endpoint}: {response.status}, {text}")
                            return None
                elif method.upper() == "POST":
                    async with session.post(url, headers=headers, json=data) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            text = await response.text()
                            logger.error(f"Ошибка POST {endpoint}: {response.status}, {text}")
                            return None
                elif method.upper() == "PUT":
                    async with session.put(url, headers=headers, json=data) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            text = await response.text()
                            logger.error(f"Ошибка PUT {endpoint}: {response.status}, {text}")
                            return None
                elif method.upper() == "DELETE":
                    async with session.delete(url, headers=headers) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            text = await response.text()
                            logger.error(f"Ошибка DELETE {endpoint}: {response.status}, {text}")
                            return None
                        
        except Exception as e:
            logger.error(f"Ошибка запроса к 3x-ui API: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def get_inbound(self, inbound_id: int = None) -> Optional[Dict]:
        """Получение информации о inbound"""
        inbound_id = inbound_id or self.inbound_id
        
        # Используем найденный через DevTools endpoint: /panel/api/inbounds/list
        # Пробуем GET и POST, так как некоторые API требуют POST даже для получения данных
        endpoints = [
            ("GET", "/panel/api/inbounds/list"),
            ("POST", "/panel/api/inbounds/list"),
        ]
        
        for method, endpoint in endpoints:
            result = await self._make_request(method, endpoint)
            if result and result.get("success"):
                inbounds = result.get("obj", [])
                logger.info(f"✅ Получен список inbounds через {method} {endpoint}: {len(inbounds)} inbounds")
                # Ищем нужный inbound по ID
                for inbound in inbounds:
                    if inbound.get("id") == inbound_id:
                        # Логируем подробную информацию о найденном inbound
                        inb_port = inbound.get('port', 'N/A')
                        inb_protocol = inbound.get('protocol', 'N/A')
                        inb_remark = inbound.get('remark', 'N/A')
                        inb_enable = inbound.get('enable', False)
                        
                        logger.info(f"✅ Найден inbound с ID {inbound_id}:")
                        logger.info(f"   - Порт: {inb_port}")
                        logger.info(f"   - Протокол: {inb_protocol}")
                        logger.info(f"   - Remark: {inb_remark}")
                        logger.info(f"   - Enabled: {inb_enable}")
                        
                        # Логируем streamSettings для отладки
                        stream_settings = inbound.get("streamSettings", {})
                        if isinstance(stream_settings, str):
                            try:
                                import json
                                stream_settings_parsed = json.loads(stream_settings)
                                security = stream_settings_parsed.get('security', 'N/A')
                                has_reality = bool(stream_settings_parsed.get('realitySettings'))
                                logger.info(f"   - Security: {security}")
                                logger.info(f"   - Reality Settings: {has_reality}")
                                logger.debug(f"📋 streamSettings (распарсено): security={security}, realitySettings={has_reality}")
                            except:
                                logger.debug(f"📋 streamSettings (строка): {stream_settings[:100]}...")
                        else:
                            security = stream_settings.get('security', 'N/A')
                            has_reality = bool(stream_settings.get('realitySettings'))
                            logger.info(f"   - Security: {security}")
                            logger.info(f"   - Reality Settings: {has_reality}")
                            logger.debug(f"📋 streamSettings (объект): security={security}, realitySettings={has_reality}")
                        return inbound
                logger.warning(f"Inbound с ID {inbound_id} не найден в списке из {len(inbounds)} inbounds")
                # Логируем все доступные inbounds с подробной информацией
                if inbounds:
                    logger.warning(f"📋 Доступные inbounds ({len(inbounds)} шт.):")
                    for idx, inb in enumerate(inbounds, 1):
                        inb_id = inb.get('id', 'N/A')
                        inb_port = inb.get('port', 'N/A')
                        inb_protocol = inb.get('protocol', 'N/A')
                        inb_remark = inb.get('remark', 'N/A')
                        inb_enable = inb.get('enable', False)
                        
                        # Проверяем streamSettings для Reality
                        stream_settings = inb.get("streamSettings", {})
                        if isinstance(stream_settings, str):
                            try:
                                stream_settings_parsed = json.loads(stream_settings)
                                security = stream_settings_parsed.get('security', 'N/A')
                                has_reality = bool(stream_settings_parsed.get('realitySettings'))
                            except:
                                security = 'N/A'
                                has_reality = False
                        else:
                            security = stream_settings.get('security', 'N/A')
                            has_reality = bool(stream_settings.get('realitySettings'))
                        
                        logger.warning(f"   {idx}. ID={inb_id}, порт={inb_port}, протокол={inb_protocol}, "
                                     f"remark={inb_remark}, enabled={inb_enable}, "
                                     f"security={security}, reality={has_reality}")
                    
                    logger.warning(f"💡 Убедитесь, что X3UI_INBOUND_ID в .env соответствует нужному inbound ID")
            elif result:
                logger.debug(f"Результат {method} {endpoint}: {result}")
        
        return None
    
    async def get_xray_config(self) -> Optional[Dict]:
        """Получение полной конфигурации Xray через API 3x-ui
        
        Если прямой endpoint для конфигурации недоступен, собираем конфигурацию из списка inbounds
        """
        try:
            # Пробуем разные варианты endpoint для получения конфигурации
            endpoints = [
                "/panel/api/xray/config",
                "/xui/api/xray/config",
                "/api/xray/config"
            ]
            
            for endpoint in endpoints:
                result = await self._make_request("GET", endpoint)
                if result:
                    # Если результат успешный, возвращаем его
                    if isinstance(result, dict):
                        # Если это обертка с success, извлекаем данные
                        if result.get("success") and "obj" in result:
                            logger.info(f"✅ Конфигурация Xray получена через {endpoint}")
                            return result.get("obj")
                        # Если это уже конфигурация напрямую
                        elif "inbounds" in result:
                            logger.info(f"✅ Конфигурация Xray получена через {endpoint}")
                            return result
            
            # Если прямой endpoint недоступен, собираем конфигурацию из списка inbounds
            logger.info("⚠️ Прямой endpoint для конфигурации недоступен, собираем из списка inbounds")
            inbounds_result = await self._make_request("GET", "/panel/api/inbounds/list")
            if inbounds_result and inbounds_result.get("success"):
                inbounds = inbounds_result.get("obj", [])
                # Преобразуем список inbounds в формат конфигурации Xray
                # Парсим settings и streamSettings из строк JSON
                parsed_inbounds = []
                for inbound in inbounds:
                    parsed_inbound = inbound.copy()
                    
                    # Парсим settings
                    if isinstance(inbound.get("settings"), str):
                        parsed_inbound["settings"] = json.loads(inbound["settings"])
                    
                    # Парсим streamSettings
                    if isinstance(inbound.get("streamSettings"), str):
                        parsed_inbound["streamSettings"] = json.loads(inbound["streamSettings"])
                    
                    # Парсим sniffing
                    if isinstance(inbound.get("sniffing"), str):
                        parsed_inbound["sniffing"] = json.loads(inbound["sniffing"])
                    
                    parsed_inbounds.append(parsed_inbound)
                
                # Формируем базовую конфигурацию Xray
                config = {
                    "inbounds": parsed_inbounds,
                    "outbounds": [
                        {
                            "protocol": "freedom",
                            "settings": {
                                "domainStrategy": "AsIs"
                            },
                            "tag": "direct"
                        },
                        {
                            "protocol": "blackhole",
                            "settings": {},
                            "tag": "blocked"
                        }
                    ],
                    "routing": {
                        "domainStrategy": "AsIs",
                        "rules": []
                    }
                }
                logger.info(f"✅ Конфигурация Xray собрана из {len(parsed_inbounds)} inbounds")
                return config
            
            return None
        except Exception as e:
            logger.error(f"Ошибка получения конфигурации Xray: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def add_client(self, uuid: str, email: str = None, inbound_id: int = None) -> tuple[bool, Optional[Dict]]:
        """Добавление клиента в inbound
        
        Returns:
            tuple: (success: bool, config: Optional[Dict]) - успех операции и полная конфигурация Xray
        """
        inbound_id = inbound_id or self.inbound_id
        
        if not email:
            email = f"user_{uuid[:8]}"
        
        try:
            # Получаем текущий inbound
            inbound = await self.get_inbound(inbound_id)
            if not inbound:
                logger.error(f"Inbound {inbound_id} не найден в 3x-ui")
                return False, None
            
            # Получаем список клиентов
            # settings может быть строкой JSON или словарем
            inbound_settings = inbound.get("settings", {})
            if isinstance(inbound_settings, str):
                import json
                inbound_settings = json.loads(inbound_settings)
            elif not isinstance(inbound_settings, dict):
                inbound_settings = {}
            
            clients = inbound_settings.get("clients", [])
            
            # Проверяем, нет ли уже такого клиента
            if any(c.get("id") == uuid for c in clients):
                logger.info(f"Пользователь {uuid} уже существует в 3x-ui")
                # Возвращаем текущую конфигурацию
                config = await self.get_xray_config()
                return True, config
            
            # Добавляем нового клиента
            new_client = {
                "id": uuid,
                "email": email,
                "enable": True,
                "expiryTime": 0,
                "limitIp": 0,
                "totalGB": 0,
                "flow": "",  # Для VLESS
                "tgId": "",
                "subId": ""
            }
            
            clients.append(new_client)
            
            # Обновляем inbound settings
            inbound_settings["clients"] = clients
            inbound["settings"] = inbound_settings
            
            # Отправляем обновление
            # Пробуем разные варианты endpoint для обновления
            # Пользователь нашел через DevTools: POST /panel/api/inbounds/add (для добавления нового inbound)
            # Для обновления существующего inbound может быть: POST /panel/api/inbounds/update/{id}
            update_endpoints = [
                f"/panel/api/inbounds/update/{inbound_id}",  # С 's' в конце (найден через DevTools)
                f"/panel/api/inbound/update/{inbound_id}",   # Без 's' (старый вариант)
            ]
            
            # Подготавливаем данные для обновления
            # API 3x-ui ожидает settings, streamSettings и sniffing как строки JSON, а не объекты!
            # Поэтому сериализуем их обратно в строки
            
            # ВАЖНО: Получаем streamSettings из исходного inbound
            # Эти параметры уже содержат все настройки Reality (security, server_name, fingerprint, publicKey, shortIds, spiderX)
            # Мы НЕ ДОЛЖНЫ их изменять, только сохранить как есть
            stream_settings = inbound.get("streamSettings", {})
            original_stream_settings_str = None
            
            if isinstance(stream_settings, str):
                # Если уже строка, сохраняем оригинальную строку
                original_stream_settings_str = stream_settings
                # Парсим только для проверки и логирования
                try:
                    stream_settings = json.loads(stream_settings)
                    logger.debug(f"✅ streamSettings распарсен из строки, размер: {len(original_stream_settings_str)} символов")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось распарсить streamSettings как JSON: {e}")
                    logger.warning(f"   Первые 200 символов: {stream_settings[:200]}")
                    # Если не удалось распарсить, используем оригинальную строку
                    stream_settings = {}
            else:
                # Если объект, сериализуем для проверки
                original_stream_settings_str = json.dumps(stream_settings, ensure_ascii=False)
                logger.debug(f"✅ streamSettings уже объект, размер после сериализации: {len(original_stream_settings_str)} символов")
            
            # Проверяем, что streamSettings содержит все необходимые параметры Reality
            if not stream_settings:
                logger.error("❌ streamSettings пуст! Это приведет к потере параметров Reality!")
                logger.error("⚠️ ВАЖНО: При обновлении inbound будут потеряны параметры Reality (security, server_name, fingerprint, public key, short id, spiderx)")
            else:
                # Логируем параметры Reality для отладки
                reality_settings = stream_settings.get("realitySettings", {})
                security = stream_settings.get("security", "")
                
                # В Xray конфигурации на сервере используется privateKey, а не publicKey
                # publicKey используется только в клиентской конфигурации
                private_key = reality_settings.get("privateKey", "")
                public_key = reality_settings.get("publicKey", "")  # Может отсутствовать на сервере
                mldsa65_seed = reality_settings.get("mldsa65Seed", "")  # Альтернативное поле
                
                logger.info(f"🔍 Параметры Reality в streamSettings перед обновлением:")
                logger.info(f"   - security: {security}")
                logger.info(f"   - serverNames: {reality_settings.get('serverNames', [])}")
                logger.info(f"   - fingerprint: {reality_settings.get('fingerprint', 'N/A')}")
                logger.info(f"   - privateKey: {'присутствует' if private_key else 'N/A'}")
                logger.info(f"   - publicKey: {'присутствует' if public_key else 'N/A'}")
                logger.info(f"   - mldsa65Seed: {'присутствует' if mldsa65_seed else 'N/A'}")
                logger.info(f"   - shortIds: {reality_settings.get('shortIds', [])}")
                logger.info(f"   - spiderX: {reality_settings.get('spiderX', 'N/A')}")
                
                # Проверяем наличие обязательных параметров Reality
                # На сервере используется privateKey, а не publicKey
                if security == "reality":
                    if not reality_settings:
                        logger.error("❌ security=reality, но realitySettings отсутствует!")
                    elif not private_key and not public_key and not mldsa65_seed:
                        logger.warning("⚠️ realitySettings: отсутствует privateKey/publicKey/mldsa65Seed (но это нормально, если используется оригинальная строка)")
                    elif not reality_settings.get("shortIds"):
                        logger.error("❌ realitySettings.shortIds отсутствует!")
                    elif not reality_settings.get("serverNames"):
                        logger.error("❌ realitySettings.serverNames отсутствует!")
                    else:
                        logger.info("✅ Все обязательные параметры Reality присутствуют")
            
            # Сериализуем обратно в строку
            # ВАЖНО: Если у нас была оригинальная строка, используем её (чтобы не потерять форматирование)
            # Иначе сериализуем объект
            if original_stream_settings_str and isinstance(stream_settings, dict) and stream_settings:
                # Если была оригинальная строка и мы успешно распарсили, используем оригинальную строку
                # Это гарантирует, что мы не потеряем никакие параметры
                stream_settings_str = original_stream_settings_str
                logger.info(f"✅ Используем оригинальную строку streamSettings (размер: {len(stream_settings_str)} символов)")
            else:
                # Если не было оригинальной строки или парсинг не удался, сериализуем объект
                stream_settings_str = json.dumps(stream_settings, ensure_ascii=False) if stream_settings else "{}"
                logger.info(f"✅ Сериализован streamSettings из объекта (размер: {len(stream_settings_str)} символов)")
            
            # Проверяем, что в строке есть все необходимые параметры Reality
            if stream_settings_str and stream_settings_str != "{}":
                has_security = "security" in stream_settings_str.lower()
                has_reality = "reality" in stream_settings_str.lower()
                has_publickey = "publickey" in stream_settings_str.lower() or "publicKey" in stream_settings_str
                has_shortids = "shortids" in stream_settings_str.lower() or "shortIds" in stream_settings_str
                has_servernames = "servernames" in stream_settings_str.lower() or "serverNames" in stream_settings_str
                
                logger.info(f"🔍 Проверка streamSettings перед отправкой:")
                logger.info(f"   - содержит 'security': {has_security}")
                logger.info(f"   - содержит 'reality': {has_reality}")
                logger.info(f"   - содержит 'publicKey': {has_publickey}")
                logger.info(f"   - содержит 'shortIds': {has_shortids}")
                logger.info(f"   - содержит 'serverNames': {has_servernames}")
                
                if has_reality and (not has_publickey or not has_shortids or not has_servernames):
                    logger.error("❌ ВНИМАНИЕ: streamSettings содержит 'reality', но отсутствуют обязательные параметры!")
            else:
                logger.error("❌ streamSettings пуст или равен '{}'!")
            
            sniffing = inbound.get("sniffing", {})
            if isinstance(sniffing, str):
                # Если уже строка, оставляем как есть
                sniffing_str = sniffing
            else:
                # Если объект, сериализуем в строку
                sniffing_str = json.dumps(sniffing) if sniffing else "{}"
            
            # settings также должен быть строкой JSON
            settings_str = json.dumps(inbound_settings)
            
            # Собираем все поля inbound для обновления
            # ВАЖНО: Сохраняем ВСЕ поля из исходного inbound, чтобы не потерять параметры Reality
            # Копируем все поля из исходного inbound, чтобы сохранить все настройки
            update_data = {
                "id": inbound_id,
                "settings": settings_str,  # Строка JSON! (обновленные clients)
                "streamSettings": stream_settings_str,  # Строка JSON! (содержит Reality параметры - БЕЗ ИЗМЕНЕНИЙ)
                "sniffing": sniffing_str,  # Строка JSON! (без изменений)
                "tag": inbound.get("tag", ""),
                "protocol": inbound.get("protocol", "vless"),
                "port": inbound.get("port", 443),
                "listen": inbound.get("listen", ""),
                "remark": inbound.get("remark", ""),
                "enable": inbound.get("enable", True)  # Важно: сохраняем статус включения inbound
            }
            
            # ВАЖНО: Копируем все остальные поля из исходного inbound
            # Это гарантирует, что мы не потеряем никакие параметры
            for key, value in inbound.items():
                if key not in update_data and key not in ["settings", "streamSettings", "sniffing"]:
                    # Копируем все остальные поля как есть
                    update_data[key] = value
                    logger.debug(f"📋 Копируем поле {key} из исходного inbound")
            
            # Логируем, что мы отправляем
            logger.debug(f"📤 Отправляем обновление inbound {inbound_id}:")
            logger.debug(f"   - protocol: {update_data['protocol']}")
            logger.debug(f"   - port: {update_data['port']}")
            logger.debug(f"   - enable: {update_data['enable']}")
            logger.debug(f"   - streamSettings размер: {len(stream_settings_str)} символов")
            logger.debug(f"   - streamSettings содержит 'reality': {'reality' in stream_settings_str.lower()}")
            logger.debug(f"   - streamSettings содержит 'security': {'security' in stream_settings_str.lower()}")
            
            result = None
            for endpoint in update_endpoints:
                result = await self._make_request("POST", endpoint, update_data)
                if result and result.get("success"):
                    logger.info(f"✅ Обновление выполнено через {endpoint}")
                    break
                elif result:
                    logger.debug(f"Результат {endpoint}: {result}")
            
            if result and result.get("success"):
                logger.info(f"✅ Пользователь {uuid} успешно добавлен в 3x-ui")
                # Перезапускаем Xray через API
                await self.restart_xray()
                # Ждем немного, чтобы Xray успел перезагрузить конфигурацию
                import asyncio
                await asyncio.sleep(2)
                # Получаем обновленную конфигурацию
                config = await self.get_xray_config()
                
                # Проверяем, что параметры Reality сохранились после обновления
                if config:
                    # Ищем наш inbound в конфигурации
                    for inbound in config.get("inbounds", []):
                        if inbound.get("port") == update_data.get("port") and inbound.get("protocol") == update_data.get("protocol"):
                            updated_stream_settings = inbound.get("streamSettings", {})
                            if isinstance(updated_stream_settings, str):
                                try:
                                    updated_stream_settings = json.loads(updated_stream_settings)
                                except:
                                    pass
                            
                            updated_security = updated_stream_settings.get("security", "")
                            updated_reality = updated_stream_settings.get("realitySettings", {})
                            
                            logger.info(f"🔍 Проверка параметров Reality после обновления:")
                            logger.info(f"   - security: {updated_security}")
                            logger.info(f"   - realitySettings присутствует: {bool(updated_reality)}")
                            if updated_reality:
                                logger.info(f"   - serverNames: {updated_reality.get('serverNames', [])}")
                                logger.info(f"   - shortIds: {updated_reality.get('shortIds', [])}")
                                # На сервере используется privateKey, а не publicKey
                                has_private_key = bool(updated_reality.get("privateKey"))
                                has_public_key = bool(updated_reality.get("publicKey"))
                                has_mldsa65_seed = bool(updated_reality.get("mldsa65Seed"))
                                logger.info(f"   - privateKey присутствует: {has_private_key}")
                                logger.info(f"   - publicKey присутствует: {has_public_key}")
                                logger.info(f"   - mldsa65Seed присутствует: {has_mldsa65_seed}")
                            
                            # Предупреждение, если параметры Reality потеряны
                            if updated_security == "reality" and not updated_reality:
                                logger.error("❌ ВНИМАНИЕ: security=reality, но realitySettings отсутствует после обновления!")
                            elif updated_security == "reality" and updated_reality:
                                # Проверяем наличие обязательных параметров
                                has_key = bool(updated_reality.get("privateKey") or updated_reality.get("publicKey") or updated_reality.get("mldsa65Seed"))
                                has_short_ids = bool(updated_reality.get("shortIds"))
                                has_server_names = bool(updated_reality.get("serverNames"))
                                
                                if not has_key or not has_short_ids or not has_server_names:
                                    logger.error("❌ ВНИМАНИЕ: realitySettings неполный после обновления!")
                                    logger.error(f"   - ключ (privateKey/publicKey/mldsa65Seed): {has_key}")
                                    logger.error(f"   - shortIds: {has_short_ids}")
                                    logger.error(f"   - serverNames: {has_server_names}")
                                else:
                                    logger.info("✅ Параметры Reality успешно сохранены")
                            break
                
                return True, config
            else:
                logger.error(f"Ошибка добавления пользователя в 3x-ui: {result}")
                return False, None
                
        except Exception as e:
            logger.error(f"Ошибка добавления клиента в 3x-ui: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, None
    
    async def remove_client(self, uuid: str, inbound_id: int = None) -> bool:
        """Удаление клиента из inbound"""
        inbound_id = inbound_id or self.inbound_id
        
        try:
            # Получаем текущий inbound
            inbound = await self.get_inbound(inbound_id)
            if not inbound:
                logger.error(f"Inbound {inbound_id} не найден в 3x-ui")
                return False
            
            # Удаляем клиента
            clients = inbound.get("settings", {}).get("clients", [])
            initial_count = len(clients)
            clients = [c for c in clients if c.get("id") != uuid]
            
            if len(clients) == initial_count:
                logger.warning(f"Пользователь {uuid} не найден в 3x-ui")
                return True
            
            # Обновляем inbound settings
            inbound_settings = inbound.get("settings", {})
            if isinstance(inbound_settings, str):
                import json
                inbound_settings = json.loads(inbound_settings)
            elif not isinstance(inbound_settings, dict):
                inbound_settings = {}
            
            inbound_settings["clients"] = clients
            
            # Сериализуем settings, streamSettings и sniffing в строки JSON (как в add_client)
            settings_str = json.dumps(inbound_settings)
            
            stream_settings = inbound.get("streamSettings", {})
            if isinstance(stream_settings, str):
                stream_settings_str = stream_settings
            else:
                stream_settings_str = json.dumps(stream_settings) if stream_settings else "{}"
            
            sniffing = inbound.get("sniffing", {})
            if isinstance(sniffing, str):
                sniffing_str = sniffing
            else:
                sniffing_str = json.dumps(sniffing) if sniffing else "{}"
            
            # Подготавливаем данные для обновления
            update_data = {
                "id": inbound_id,
                "settings": settings_str,  # Строка JSON!
                "streamSettings": stream_settings_str,  # Строка JSON!
                "sniffing": sniffing_str,  # Строка JSON!
                "tag": inbound.get("tag", ""),
                "protocol": inbound.get("protocol", "vmess"),
                "port": inbound.get("port", 443),
                "listen": inbound.get("listen", ""),
                "remark": inbound.get("remark", ""),
                "enable": inbound.get("enable", True),  # Важно: сохраняем статус включения inbound
                "expiryTime": inbound.get("expiryTime", 0),
                "clientStats": inbound.get("clientStats", []),
                "up": inbound.get("up", 0),
                "down": inbound.get("down", 0),
                "total": inbound.get("total", 0)
            }
            
            # Отправляем обновление
            result = await self._make_request("POST", f"/panel/api/inbound/update/{inbound_id}", update_data)
            
            if result and result.get("success"):
                logger.info(f"✅ Пользователь {uuid} успешно удален из 3x-ui")
                # Перезапускаем Xray через API
                await self.restart_xray()
                return True
            else:
                logger.error(f"Ошибка удаления пользователя из 3x-ui: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка удаления клиента из 3x-ui: {e}")
            return False
    
    async def restart_xray(self) -> bool:
        """Перезапуск Xray через API 3x-ui"""
        try:
            # Пробуем разные варианты endpoint для перезапуска Xray
            endpoints = [
                "/panel/api/inbounds/restartAll",  # Перезапуск всех inbounds
                "/panel/api/xray/restart",  # Старый вариант
                "/xui/api/xray/restart",  # Альтернативный вариант
                "/api/xray/restart"  # Еще один вариант
            ]
            
            for endpoint in endpoints:
                result = await self._make_request("POST", endpoint)
                if result and result.get("success"):
                    logger.info(f"✅ Xray успешно перезапущен через {endpoint}")
                    return True
                elif result:
                    logger.debug(f"Результат {endpoint}: {result}")
            
            # Если ни один endpoint не сработал, выводим предупреждение
            logger.warning(f"⚠️ Не удалось перезапустить Xray через API. Попробованы endpoints: {endpoints}")
            logger.warning("💡 Xray может перезапуститься автоматически при обновлении inbound, или перезапустите вручную через панель")
            return False
        except Exception as e:
            logger.error(f"Ошибка перезапуска Xray через 3x-ui API: {e}")
            return False
    
    async def get_client_link(self, uuid: str, inbound_id: int = None) -> Optional[str]:
        """Получение ссылки клиента из 3x-ui"""
        inbound_id = inbound_id or self.inbound_id
        
        try:
            result = await self._make_request("GET", f"/panel/api/inbound/clientIps/{uuid}")
            if result and result.get("success"):
                # Получаем клиента из inbound
                inbound = await self.get_inbound(inbound_id)
                if inbound:
                    clients = inbound.get("settings", {}).get("clients", [])
                    client = next((c for c in clients if c.get("id") == uuid), None)
                    if client:
                        # Генерируем ссылку vmess
                        # 3x-ui может вернуть готовую ссылку через другой endpoint
                        pass
            return None
        except Exception as e:
            logger.error(f"Ошибка получения ссылки клиента: {e}")
            return None
