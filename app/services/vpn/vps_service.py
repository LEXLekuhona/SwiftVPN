import json
import asyncio
import paramiko
import sqlite3
from typing import Optional, Dict
from loguru import logger
from config.settings import settings


class VPSService:
    """Сервис для автоматического управления VPS через SSH или 3x-ui API"""
    
    def __init__(self):
        self.use_x3ui = getattr(settings, 'USE_X3UI_API', True)  # Используем API по умолчанию
        
        if self.use_x3ui:
            # Используем 3x-ui API
            from app.services.vpn import X3UIService
            self.x3ui_service = X3UIService()
            logger.info("Используется 3x-ui API для управления пользователями")
        else:
            # Используем SSH для работы с 3x-ui конфигурацией Xray
            self.host = getattr(settings, 'VPS_HOST', '148.253.213.153')
            self.port = getattr(settings, 'VPS_SSH_PORT', 22)
            self.username = getattr(settings, 'VPS_USERNAME', 'root')
            self.password = getattr(settings, 'VPS_PASSWORD', '')
            self.ssh_key_path = getattr(settings, 'VPS_SSH_KEY_PATH', '')
            # Путь будет определяться динамически через _get_xray_config_path
            logger.info("Используется SSH для управления пользователями через 3x-ui конфигурацию")
    
    def _get_ssh_client(self) -> Optional[paramiko.SSHClient]:
        """Создание SSH подключения"""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Подключение по ключу или паролю
            if self.ssh_key_path:
                client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    key_filename=self.ssh_key_path,
                    timeout=10
                )
            elif self.password:
                client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=10
                )
            else:
                logger.error("Не указан пароль или SSH ключ для VPS")
                return None
            
            return client
            
        except Exception as e:
            logger.error(f"Ошибка подключения к VPS: {e}")
            return None
    
    async def _get_xray_config_path(self, client: paramiko.SSHClient) -> Optional[str]:
        """Определяет путь к файлу конфигурации Xray, используемому 3x-ui"""
        try:
            # Проверяем стандартные пути
            possible_paths = [
                '/usr/local/x-ui/bin/config.json',
                '/etc/x-ui/config.json',
                '/opt/x-ui/config.json'
            ]
            for path in possible_paths:
                stdin, stdout, stderr = client.exec_command(f"test -f {path} && echo 'found'")
                if stdout.read().decode().strip() == 'found':
                    logger.info(f"Найден файл конфигурации Xray: {path}")
                    return path
            
            # Если не найдено, пытаемся найти через процесс Xray
            stdin, stdout, stderr = client.exec_command("ps aux | grep xray | grep -v grep")
            output = stdout.read().decode().strip()
            import re
            match = re.search(r'-c\s+(\S+)', output)
            if match:
                config_path = match.group(1)
                logger.info(f"Найден файл конфигурации Xray через процесс: {config_path}")
                return config_path
            
            logger.warning("Не удалось определить путь к файлу конфигурации Xray.")
            return None
        except Exception as e:
            logger.error(f"Ошибка определения пути к конфигурации Xray: {e}")
            return None
    
    async def update_user_expiry(self, uuid: str, expiry_time_ms: int) -> bool:
        """Обновление срока действия клиента в 3x-ui."""
        if self.use_x3ui:
            return await self.x3ui_service.update_client_expiry(uuid, expiry_time_ms)
        logger.warning("Обновление срока через SSH не реализовано")
        return False

    async def add_user_to_v2ray(
        self,
        uuid: str,
        email: str = None,
        protocol_type: str = "vless",
        port: int = 443,
        expiry_time_ms: int = 0,
    ) -> tuple[bool, Optional[Dict]]:
        """Добавление пользователя в конфигурацию V2Ray/Xray на VPS
        
        Returns:
            tuple: (success: bool, config: Optional[Dict]) - успех операции и полная конфигурация Xray
        """
        if not email:
            email = f"user_{uuid[:8]}"
        
        # Используем 3x-ui API, если включено
        if self.use_x3ui:
            success, config = await self.x3ui_service.add_client(
                uuid, email, expiry_time_ms=expiry_time_ms
            )
            if success and config:
                logger.info(f"✅ Пользователь {uuid} добавлен через API, получена конфигурация Xray")
                logger.debug(f"Конфигурация содержит {len(config.get('inbounds', []))} inbounds")
            return success, config
        
        # Иначе используем SSH (старый метод)
        client = self._get_ssh_client()
        if not client:
            return False, None
        
        try:
            # Определяем путь к конфигурации
            config_path = await self._get_xray_config_path(client)
            if not config_path:
                logger.error("Не удалось найти файл конфигурации Xray")
                return False, None
            
            # Читаем текущую конфигурацию
            sftp = client.open_sftp()
            try:
                with sftp.open(config_path, 'r') as f:
                    config_content = f.read().decode('utf-8')
            except FileNotFoundError:
                logger.error(f"Файл конфигурации не найден: {config_path}")
                return False, None
            
            config = json.loads(config_content)
            
            # Логируем все найденные inbounds для отладки
            inbounds_list = config.get('inbounds', []) or []
            logger.info(f"📋 Найдено inbounds: {len(inbounds_list)}")
            for idx, inbound in enumerate(inbounds_list):
                settings = inbound.get('settings') or {}
                clients = settings.get('clients') or []
                logger.info(f"  Inbound {idx}: порт={inbound.get('port')}, протокол={inbound.get('protocol')}, клиентов={len(clients)}")
            
            # Находим нужный inbound по порту и протоколу
            # Если указан индекс 5, используем его (для случаев, когда нужно использовать конкретный inbound)
            target_inbound = None
            inbound_index = None
            
            # Сначала пробуем найти по порту и протоколу
            for i, inbound in enumerate(config.get("inbounds", [])):
                if inbound.get("port") == port and inbound.get("protocol", "").lower() == protocol_type.lower():
                    target_inbound = inbound
                    inbound_index = i
                    logger.info(f"✅ Найден целевой inbound: индекс={i}, порт={port}, протокол={protocol_type}")
                    break
            
            # Если не найден, пробуем использовать индекс 5 (если он существует)
            if not target_inbound and len(config.get("inbounds", [])) > 5:
                inbound_index = 5
                inbounds_list = config.get("inbounds", [])
                if len(inbounds_list) > 5:
                    target_inbound = inbounds_list[5]
                    logger.info(f"✅ Используем inbound с индексом 5: порт={target_inbound.get('port')}, протокол={target_inbound.get('protocol')}")
            
            if not target_inbound:
                logger.warning(f"⚠️ Не найден inbound с портом {port} и протоколом {protocol_type}")
                # Пробуем найти первый inbound с нужным протоколом
                for i, inbound in enumerate(config.get("inbounds", [])):
                    if inbound.get("protocol", "").lower() == protocol_type.lower():
                        target_inbound = inbound
                        inbound_index = i
                        logger.warning(f"⚠️ Найден inbound с протоколом {protocol_type}, но порт {inbound.get('port')} отличается от {port}")
                        break
                
                if not target_inbound:
                    logger.error(f"❌ Не найден inbound с протоколом {protocol_type}")
                    logger.error(f"Доступные протоколы: {[inb.get('protocol') for inb in config.get('inbounds', [])]}")
                    return False, None
            
            # Получаем список клиентов из найденного inbound
            settings = target_inbound.get("settings") or {}
            clients = settings.get("clients") or []
            existing_uuids = [c.get("id") for c in clients if c and c.get("id")]
            existing_emails = [c.get("email") for c in clients if c and c.get("email")]
            
            if uuid in existing_uuids:
                logger.info(f"Пользователь {uuid} уже существует на VPS")
                return True, config
            
            # Проверяем, нет ли пользователя с таким же email
            if email in existing_emails:
                logger.warning(f"Email {email} уже используется. Генерируем новый уникальный email.")
                email = f"user_{uuid[:8]}"
            
            # Добавляем пользователя (VLESS не требует alterId)
            if protocol_type.lower() == "vless":
                new_client = {
                    "id": uuid,
                    "email": email
                }
                # Добавляем flow, если он указан в настройках
                target_settings = target_inbound.get("settings") or {}
                target_clients = target_settings.get("clients") or []
                if target_clients and len(target_clients) > 0:
                    # Берем flow из первого клиента, если он есть
                    first_client = target_clients[0]
                    if first_client and first_client.get("flow"):
                        new_client["flow"] = first_client.get("flow")
            else:
                # VMess требует alterId
                new_client = {
                    "id": uuid,
                    "alterId": 0,
                    "email": email
                }
            
            clients.append(new_client)
            logger.info(f"➕ Добавлен новый клиент: UUID={uuid}, email={email}, всего клиентов={len(clients)}")
            
            # Сохраняем конфигурацию обратно в нужный inbound
            config["inbounds"][inbound_index]["settings"]["clients"] = clients
            logger.info(f"💾 Конфигурация обновлена, готовимся к записи в {config_path}")
            
            # Добавляем DNS настройки, если их нет
            if "dns" not in config:
                config["dns"] = {
                    "servers": [
                        "8.8.8.8",
                        "8.8.4.4",
                        "1.1.1.1",
                        {
                            "address": "223.5.5.5",
                            "domains": ["geosite:cn"]
                        }
                    ],
                    "queryStrategy": "UseIP"
                }
            
            # Улучшаем outbound с правильной стратегией DNS
            if "outbounds" not in config or len(config["outbounds"]) == 0:
                config["outbounds"] = []
            
            # Обновляем или создаем outbound
            if len(config["outbounds"]) > 0:
                config["outbounds"][0]["protocol"] = "freedom"
                if "settings" not in config["outbounds"][0]:
                    config["outbounds"][0]["settings"] = {}
                config["outbounds"][0]["settings"]["domainStrategy"] = "UseIPv4"
                config["outbounds"][0]["tag"] = "direct"
            else:
                config["outbounds"].append({
                    "protocol": "freedom",
                    "settings": {
                        "domainStrategy": "UseIPv4"
                    },
                    "tag": "direct"
                })
            
            # Добавляем routing с правильными правилами
            if "routing" not in config:
                config["routing"] = {
                    "domainStrategy": "IPIfNonMatch",
                    "rules": [
                        {
                            "type": "field",
                            "outboundTag": "direct",
                            "network": "tcp,udp"
                        }
                    ]
                }
            else:
                # Обновляем существующий routing
                config["routing"]["domainStrategy"] = "IPIfNonMatch"
                if "rules" not in config["routing"]:
                    config["routing"]["rules"] = []
                # Добавляем правило, если его нет
                has_direct_rule = any(
                    rule.get("outboundTag") == "direct" 
                    for rule in config["routing"].get("rules", [])
                )
                if not has_direct_rule:
                    config["routing"]["rules"].append({
                        "type": "field",
                        "outboundTag": "direct",
                        "network": "tcp,udp"
                    })
            
            new_config_content = json.dumps(config, indent=2)
            
            # Записываем обратно
            logger.info(f"📝 Записываем конфигурацию в {config_path}...")
            with sftp.open(config_path, 'w') as f:
                f.write(new_config_content.encode('utf-8'))
            
            # Проверяем, что файл записан
            sftp.close()
            logger.info(f"✅ Конфигурация записана в {config_path}")
            
            # Проверяем содержимое после записи (для отладки)
            sftp = client.open_sftp()
            with sftp.open(config_path, 'r') as f:
                verify_content = f.read().decode('utf-8')
                verify_config = json.loads(verify_content)
                verify_inbounds = verify_config.get("inbounds") or []
                if inbound_index is not None and inbound_index < len(verify_inbounds):
                    verify_inbound = verify_inbounds[inbound_index]
                    verify_settings = verify_inbound.get("settings") or {}
                    verify_clients = verify_settings.get("clients") or []
                    logger.info(f"✅ Проверка: в файле теперь {len(verify_clients)} клиентов")
                    if uuid in [c.get("id") for c in verify_clients if c]:
                        logger.info(f"✅ UUID {uuid} подтвержден в файле конфигурации")
                    else:
                        logger.error(f"❌ UUID {uuid} НЕ найден в файле после записи!")
                else:
                    logger.warning(f"⚠️ Не удалось проверить UUID {uuid} - inbound_index {inbound_index} вне диапазона")
            sftp.close()
            
            # ВАЖНО: 3x-ui перезаписывает JSON из SQLite базы данных при перезапуске
            # Нужно также обновить SQLite базу данных 3x-ui
            logger.info("💾 Обновляем SQLite базу данных 3x-ui...")
            db_paths = [
                '/usr/local/x-ui/bin/x-ui.db',
                '/etc/x-ui/x-ui.db',
                '/usr/local/x-ui/x-ui.db'
            ]
            
            db_updated = False
            for db_path in db_paths:
                try:
                    stdin, stdout, stderr = client.exec_command(f"test -f {db_path} && echo 'found'")
                    if stdout.read().decode().strip() == 'found':
                        logger.info(f"📦 Найдена база данных 3x-ui: {db_path}")
                        # Скачиваем базу данных, обновляем и загружаем обратно
                        sftp = client.open_sftp()
                        try:
                            # Скачиваем базу данных
                            local_db = f"/tmp/x-ui-{uuid[:8]}.db"
                            sftp.get(db_path, local_db)
                            
                            # Обновляем базу данных локально
                            conn = sqlite3.connect(local_db)
                            cursor = conn.cursor()
                            
                            # Находим inbound по порту и протоколу в базе данных
                            cursor.execute("SELECT id, settings FROM inbounds WHERE port = ? AND protocol = ?", (port, protocol_type))
                            inbound_row = cursor.fetchone()
                            
                            if inbound_row:
                                inbound_id, inbound_settings_json = inbound_row
                                inbound_settings = json.loads(inbound_settings_json)
                                clients = inbound_settings.get("clients", [])
                                
                                # Проверяем, нет ли уже такого UUID
                                if not any(c.get("id") == uuid for c in clients if c):
                                    # Добавляем клиента
                                    new_client = {"id": uuid, "email": email}
                                    target_settings = target_inbound.get("settings") or {}
                                    target_clients = target_settings.get("clients") or []
                                    if protocol_type.lower() == "vless" and target_clients and len(target_clients) > 0:
                                        first_client = target_clients[0]
                                        if first_client and first_client.get("flow"):
                                            new_client["flow"] = first_client.get("flow")
                                    elif protocol_type.lower() == "vmess":
                                        new_client["alterId"] = 0
                                    
                                    clients.append(new_client)
                                    inbound_settings["clients"] = clients
                                    
                                    # Обновляем базу данных
                                    cursor.execute("UPDATE inbounds SET settings = ? WHERE id = ?", 
                                                 (json.dumps(inbound_settings), inbound_id))
                                    conn.commit()
                                    logger.info(f"✅ Клиент добавлен в SQLite базу данных (inbound_id={inbound_id})")
                                    db_updated = True
                                else:
                                    logger.info(f"✅ Клиент уже существует в SQLite базе данных")
                                    db_updated = True
                            else:
                                logger.warning(f"⚠️ Inbound не найден в SQLite базе данных")
                            
                            conn.close()
                            
                            # Загружаем обновленную базу данных обратно
                            if db_updated:
                                sftp.put(local_db, db_path)
                                logger.info(f"✅ SQLite база данных обновлена")
                            
                            sftp.close()
                            break
                        except Exception as e:
                            logger.error(f"Ошибка обновления SQLite базы данных: {e}")
                            sftp.close()
                except Exception as e:
                    continue
            
            if not db_updated:
                logger.warning("⚠️ Не удалось обновить SQLite базу данных 3x-ui. Пользователь добавлен только в JSON файл.")
            
            # Перезапускаем Xray через 3x-ui
            logger.info("🔄 Перезапускаем x-ui...")
            stdin, stdout, stderr = client.exec_command('systemctl restart x-ui')
            exit_status = stdout.channel.recv_exit_status()
            error_output = stderr.read().decode('utf-8')
            stdout_output = stdout.read().decode('utf-8')
            
            if exit_status == 0:
                logger.info(f"✅ x-ui перезапущен успешно")
                # Ждем немного, чтобы x-ui успел перезагрузить конфигурацию
                await asyncio.sleep(3)
                
                # Проверяем статус x-ui
                stdin, stdout, stderr = client.exec_command('systemctl is-active x-ui')
                status = stdout.read().decode('utf-8').strip()
                if status == 'active':
                    logger.info(f"✅ x-ui активен после перезапуска")
                else:
                    logger.warning(f"⚠️ x-ui статус после перезапуска: {status}")
                
                # Проверяем, что пользователь все еще в конфигурации
                sftp = client.open_sftp()
                with sftp.open(config_path, 'r') as f:
                    final_content = f.read().decode('utf-8')
                    final_config = json.loads(final_content)
                    final_inbounds = final_config.get("inbounds") or []
                    if inbound_index is not None and inbound_index < len(final_inbounds):
                        final_inbound = final_inbounds[inbound_index]
                        final_settings = final_inbound.get("settings") or {}
                        final_clients = final_settings.get("clients") or []
                        if uuid in [c.get("id") for c in final_clients if c]:
                            logger.info(f"✅ Пользователь {uuid} успешно добавлен на VPS и x-ui перезапущен")
                            sftp.close()
                            return True, final_config
                        else:
                            # UUID не найден в клиентах, но inbound существует
                            if db_updated:
                                logger.warning(f"⚠️ Пользователь {uuid} исчез из JSON, но добавлен в SQLite базу данных")
                                logger.info("✅ Пользователь должен появиться после следующего перезапуска x-ui")
                                sftp.close()
                                return True, final_config
                            else:
                                logger.error(f"❌ Пользователь {uuid} исчез из конфигурации после перезапуска x-ui!")
                                logger.error("⚠️ Возможно, 3x-ui перезаписывает конфигурацию. Проверьте настройки 3x-ui.")
                                sftp.close()
                                return False, None
                    else:
                        # inbound_index вне диапазона
                        if db_updated:
                            logger.warning(f"⚠️ Не удалось проверить пользователя {uuid}, но он добавлен в SQLite базу данных")
                            logger.info("✅ Пользователь должен появиться после следующего перезапуска x-ui")
                            sftp.close()
                            return True, final_config
                        else:
                            logger.error(f"❌ Не удалось проверить пользователя {uuid} и он не добавлен в SQLite базу данных")
                            sftp.close()
                            return False, None
            else:
                logger.error(f"❌ Ошибка перезапуска x-ui: exit_status={exit_status}")
                logger.error(f"stderr: {error_output}")
                logger.error(f"stdout: {stdout_output}")
                
                # Пробуем альтернативные методы перезапуска
                logger.info("🔄 Пробуем альтернативный метод перезапуска...")
                stdin, stdout, stderr = client.exec_command('x-ui restart 2>&1 || systemctl restart xray 2>&1')
                exit_status2 = stdout.channel.recv_exit_status()
                if exit_status2 == 0:
                    logger.info(f"✅ x-ui/xray перезапущен альтернативным методом")
                    await asyncio.sleep(2)
                    # Читаем финальную конфигурацию
                    sftp = client.open_sftp()
                    with sftp.open(config_path, 'r') as f:
                        final_config = json.loads(f.read().decode('utf-8'))
                    sftp.close()
                    return True, final_config
                else:
                    logger.error(f"❌ Не удалось перезапустить x-ui/xray. Пользователь добавлен, но требуется ручной перезапуск.")
                    logger.error("⚠️ Выполните вручную: systemctl restart x-ui")
                    # Читаем конфигурацию, даже если перезапуск не удался
                    sftp = client.open_sftp()
                    with sftp.open(config_path, 'r') as f:
                        final_config = json.loads(f.read().decode('utf-8'))
                    sftp.close()
                    return True, final_config  # Возвращаем True, так как пользователь добавлен в файл
            
        except Exception as e:
            logger.error(f"Ошибка добавления пользователя на VPS: {e}")
            return False, None
        finally:
            client.close()
    
    async def remove_user_from_v2ray(self, uuid: str) -> bool:
        """Удаление пользователя из конфигурации V2Ray/Xray через SQLite 3x-ui"""
        if self.use_x3ui:
            logger.error("3x-ui API не работает, используем SSH для управления конфигурацией.")
            self.use_x3ui = False
        
        client = self._get_ssh_client()
        if not client:
            return False
        
        try:
            # Находим базу данных 3x-ui
            xui_db_paths = [
                '/usr/local/x-ui/bin/x-ui.db',
                '/etc/x-ui/x-ui.db',
                '/usr/local/x-ui/x-ui.db'
            ]
            
            xui_db_path = None
            for path in xui_db_paths:
                stdin, stdout, stderr = client.exec_command(f"test -f {path} && echo 'found'")
                if stdout.read().decode().strip() == 'found':
                    xui_db_path = path
                    logger.info(f"📦 Найдена база данных 3x-ui: {xui_db_path}")
                    break
            
            if not xui_db_path:
                logger.error("Не удалось найти файл базы данных 3x-ui.")
                return False
            
            # Скачиваем базу данных
            local_db_path = f"/tmp/x-ui_remove_{uuid[:8]}.db"
            sftp = client.open_sftp()
            logger.info(f"⬇️ Скачиваем базу данных 3x-ui для удаления пользователя {uuid}...")
            sftp.get(xui_db_path, local_db_path)
            logger.info("✅ База данных успешно скачана.")
            
            # Обновляем базу данных локально
            conn = sqlite3.connect(local_db_path)
            cursor = conn.cursor()
            
            # Находим и удаляем пользователя из всех inbounds
            cursor.execute("SELECT id, settings FROM inbounds")
            inbounds_data = cursor.fetchall()
            
            removed = False
            for inbound_id, settings_json in inbounds_data:
                settings = json.loads(settings_json)
                clients = settings.get("clients", [])
                initial_clients_count = len(clients)
                
                # Удаляем клиента с указанным UUID
                settings["clients"] = [c for c in clients if c.get("id") != uuid]
                
                if len(settings["clients"]) < initial_clients_count:
                    updated_settings_json = json.dumps(settings)
                    cursor.execute("UPDATE inbounds SET settings = ? WHERE id = ?", (updated_settings_json, inbound_id))
                    removed = True
                    logger.info(f"✅ Пользователь {uuid} удален из inbound {inbound_id} в локальной базе данных.")
            
            if not removed:
                logger.warning(f"Пользователь {uuid} не найден в базе данных 3x-ui. Удаление не требуется.")
                conn.close()
                sftp.close()
                client.close()
                return True
            
            conn.commit()
            conn.close()
            
            # Загружаем обновленную базу данных обратно
            logger.info(f"⬆️ Загружаем обновленную базу данных после удаления пользователя {uuid}...")
            sftp.put(local_db_path, xui_db_path)
            logger.info("✅ База данных успешно загружена на VPS.")
            
            sftp.close()
            
            # Перезапускаем x-ui
            if await self.restart_xray_service(client):
                logger.info(f"✅ Пользователь {uuid} успешно удален из Xray и сервис перезапущен.")
                client.close()
                return True
            else:
                logger.error(f"Ошибка перезапуска Xray после удаления пользователя {uuid}.")
                client.close()
                return False
                
        except Exception as e:
            logger.error(f"Ошибка удаления пользователя с VPS через SQLite: {e}")
            return False
        finally:
            if 'sftp' in locals():
                sftp.close()
            if 'client' in locals():
                client.close()
            # Удаляем временный файл
            import os
            if 'local_db_path' in locals() and os.path.exists(local_db_path):
                os.remove(local_db_path)
    
    async def restart_xray_service(self, client: paramiko.SSHClient) -> bool:
        """Перезапускает сервис x-ui на сервере."""
        try:
            stdin, stdout, stderr = client.exec_command('systemctl restart x-ui')
            exit_status = stdout.channel.recv_exit_status()
            error_output = stderr.read().decode('utf-8')
            stdout_output = stdout.read().decode('utf-8')
            
            if exit_status == 0:
                logger.info("✅ Сервис x-ui успешно перезапущен.")
                # Ждем немного, чтобы x-ui успел перезагрузить конфигурацию
                await asyncio.sleep(3)
                
                # Проверяем статус x-ui
                stdin, stdout, stderr = client.exec_command('systemctl is-active x-ui')
                status = stdout.read().decode('utf-8').strip()
                if status == 'active':
                    logger.info("✅ x-ui активен после перезапуска")
                    return True
                else:
                    logger.warning(f"⚠️ x-ui статус после перезапуска: {status}")
                    return True  # Возвращаем True, так как перезапуск выполнен
            else:
                logger.error(f"Ошибка перезапуска сервиса x-ui: {error_output}")
                return False
        except Exception as e:
            logger.error(f"Ошибка при выполнении команды перезапуска x-ui: {e}")
            return False
    
    async def check_v2ray_status(self) -> bool:
        """Проверка статуса Xray/V2Ray на сервере"""
        if self.use_x3ui:
            # Проверяем через 3x-ui API
            try:
                result = await self.x3ui_service._make_request("GET", "/panel/api/xray/config")
                return result is not None and result.get("success", False)
            except:
                return False
        
        # Иначе проверяем через SSH
        client = self._get_ssh_client()
        if not client:
            return False
        
        try:
            # Проверяем статус Xray (приоритет) или V2Ray
            stdin, stdout, stderr = client.exec_command('systemctl is-active xray || systemctl is-active v2ray')
            status = stdout.read().decode('utf-8').strip()
            client.close()
            return status == 'active'
        except Exception as e:
            logger.error(f"Ошибка проверки статуса Xray/V2Ray: {e}")
            return False
