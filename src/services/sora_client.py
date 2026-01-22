"""Sora API client module"""
import asyncio
import base64
import hashlib
import json
import io
import time
import random
import string
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
from uuid import uuid4
from urllib.request import Request, urlopen, build_opener, ProxyHandler
from urllib.error import HTTPError, URLError
from http.client import IncompleteRead
from curl_cffi.requests import AsyncSession
from curl_cffi import CurlMime
from .proxy_manager import ProxyManager
from .captcha_service import YesCaptchaService
from ..core.config import config
from ..core.logger import debug_logger

# PoW related constants
POW_MAX_ITERATION = 500000
POW_CORES = [8, 16, 24, 32]
POW_SCRIPTS = [
    "https://cdn.oaistatic.com/_next/static/cXh69klOLzS0Gy2joLDRS/_ssgManifest.js?dpl=453ebaec0d44c2decab71692e1bfe39be35a24b3"
]
POW_DPL = ["prod-f501fe933b3edf57aea882da888e1a544df99840"]
POW_NAVIGATOR_KEYS = [
    "registerProtocolHandler−function registerProtocolHandler() { [native code] }",
    "storage−[object StorageManager]",
    "locks−[object LockManager]",
    "appCodeName−Mozilla",
    "permissions−[object Permissions]",
    "webdriver−false",
    "vendor−Google Inc.",
    "mediaDevices−[object MediaDevices]",
    "cookieEnabled−true",
    "product−Gecko",
    "productSub−20030107",
    "hardwareConcurrency−32",
    "onLine−true",
]
POW_DOCUMENT_KEYS = ["_reactListeningo743lnnpvdg", "location"]
POW_WINDOW_KEYS = [
    "0", "window", "self", "document", "name", "location",
    "navigator", "screen", "innerWidth", "innerHeight",
    "localStorage", "sessionStorage", "crypto", "performance",
    "fetch", "setTimeout", "setInterval", "console",
]

# User-Agent pools
DESKTOP_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

MOBILE_USER_AGENTS = [
    "Sora/1.2026.007 (Android 15; 24122RKC7C; build 2600700)",
    "Sora/1.2026.007 (Android 14; SM-G998B; build 2600700)",
    "Sora/1.2026.007 (Android 15; Pixel 8 Pro; build 2600700)",
    "Sora/1.2026.007 (Android 14; Pixel 7; build 2600700)",
    "Sora/1.2026.007 (Android 15; 2211133C; build 2600700)",
    "Sora/1.2026.007 (Android 14; SM-S918B; build 2600700)",
    "Sora/1.2026.007 (Android 15; OnePlus 12; build 2600700)",
]

class SoraClient:
    """Sora API client with proxy support"""

    CHATGPT_BASE_URL = "https://chatgpt.com"
    SENTINEL_FLOW = "sora_2_create_task"

    def __init__(self, proxy_manager: ProxyManager, db=None):
        self.proxy_manager = proxy_manager
        self.db = db
        self.base_url = config.sora_base_url
        self.timeout = config.sora_timeout

    @staticmethod
    def _get_pow_parse_time() -> str:
        """Generate time string for PoW (EST timezone)"""
        now = datetime.now(timezone(timedelta(hours=-5)))
        return now.strftime("%a %b %d %Y %H:%M:%S") + " GMT-0500 (Eastern Standard Time)"

    @staticmethod
    def _get_pow_config(user_agent: str) -> list:
        """Generate PoW config array with browser fingerprint"""
        return [
            random.choice([1920 + 1080, 2560 + 1440, 1920 + 1200, 2560 + 1600]),
            SoraClient._get_pow_parse_time(),
            4294705152,
            0,  # [3] dynamic
            user_agent,
            random.choice(POW_SCRIPTS) if POW_SCRIPTS else "",
            random.choice(POW_DPL) if POW_DPL else None,
            "en-US",
            "en-US,es-US,en,es",
            0,  # [9] dynamic
            random.choice(POW_NAVIGATOR_KEYS),
            random.choice(POW_DOCUMENT_KEYS),
            random.choice(POW_WINDOW_KEYS),
            time.perf_counter() * 1000,
            str(uuid4()),
            "",
            random.choice(POW_CORES),
            time.time() * 1000 - (time.perf_counter() * 1000),
        ]

    @staticmethod
    def _solve_pow(seed: str, difficulty: str, config_list: list) -> Tuple[str, bool]:
        """Execute PoW calculation using SHA3-512 hash collision"""
        diff_len = len(difficulty) // 2
        seed_encoded = seed.encode()
        target_diff = bytes.fromhex(difficulty)

        static_part1 = (json.dumps(config_list[:3], separators=(',', ':'), ensure_ascii=False)[:-1] + ',').encode()
        static_part2 = (',' + json.dumps(config_list[4:9], separators=(',', ':'), ensure_ascii=False)[1:-1] + ',').encode()
        static_part3 = (',' + json.dumps(config_list[10:], separators=(',', ':'), ensure_ascii=False)[1:]).encode()

        for i in range(POW_MAX_ITERATION):
            dynamic_i = str(i).encode()
            dynamic_j = str(i >> 1).encode()

            final_json = static_part1 + dynamic_i + static_part2 + dynamic_j + static_part3
            b64_encoded = base64.b64encode(final_json)

            hash_value = hashlib.sha3_512(seed_encoded + b64_encoded).digest()

            if hash_value[:diff_len] <= target_diff:
                return b64_encoded.decode(), True

        error_token = "wQ8Lk5FbGpA2NcR9dShT6gYjU7VxZ4D" + base64.b64encode(f'"{seed}"'.encode()).decode()
        return error_token, False

    @staticmethod
    def _get_pow_token(user_agent: str) -> str:
        """Generate initial PoW token"""
        config_list = SoraClient._get_pow_config(user_agent)
        seed = format(random.random())
        difficulty = "0fffff"
        solution, _ = SoraClient._solve_pow(seed, difficulty, config_list)
        return "gAAAAAC" + solution

    @staticmethod
    def _build_sentinel_token(
        flow: str,
        req_id: str,
        pow_token: str,
        resp: Dict[str, Any],
        user_agent: str,
    ) -> str:
        """Build openai-sentinel-token from PoW response"""
        final_pow_token = pow_token

        # Check if PoW is required
        proofofwork = resp.get("proofofwork", {})
        if proofofwork.get("required"):
            seed = proofofwork.get("seed", "")
            difficulty = proofofwork.get("difficulty", "")
            if seed and difficulty:
                config_list = SoraClient._get_pow_config(user_agent)
                solution, success = SoraClient._solve_pow(seed, difficulty, config_list)
                final_pow_token = "gAAAAAB" + solution
                if not success:
                    debug_logger.log_warning("PoW calculation failed, using error token")

        if not final_pow_token.endswith("~S"):
            final_pow_token = final_pow_token + "~S"

        token_payload = {
            "p": final_pow_token,
            "t": resp.get("turnstile", {}).get("dx", ""),
            "c": resp.get("token", ""),
            "id": req_id,
            "flow": flow,
        }
        return json.dumps(token_payload, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _post_json_sync(url: str, headers: dict, payload: dict, timeout: int, proxy: Optional[str]) -> Dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers=headers, method="POST")

        try:
            if proxy:
                opener = build_opener(ProxyHandler({"http": proxy, "https": proxy}))
                resp = opener.open(req, timeout=timeout)
            else:
                resp = urlopen(req, timeout=timeout)

            # Read response with error handling for incomplete reads
            try:
                resp_text = resp.read().decode("utf-8")
            except Exception as read_error:
                # Handle IncompleteRead and other read errors
                error_msg = str(read_error)
                if "IncompleteRead" in error_msg:
                    # Try to read what we can
                    try:
                        partial_data = resp.read(999999)  # Try to read remaining data
                        resp_text = partial_data.decode("utf-8", errors="ignore")
                        debug_logger.log_error(
                            error_message=f"IncompleteRead occurred, partial data read: {len(resp_text)} bytes",
                            status_code=0,
                            response_text=resp_text[:500] if resp_text else "No data"
                        )
                    except:
                        resp_text = ""
                    # If we have partial data, try to parse it
                    if resp_text:
                        try:
                            return json.loads(resp_text)
                        except:
                            pass
                raise Exception(f"Failed to read response: {error_msg}")
            
            if resp.status not in (200, 201):
                raise Exception(f"Request failed: {resp.status} {resp_text}")
            return json.loads(resp_text)
        except HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", errors="ignore")
            except Exception as read_error:
                # Handle IncompleteRead in error response
                body = f"Failed to read error response: {str(read_error)}"
            raise Exception(f"HTTP Error: {exc.code} {body}") from exc
        except URLError as exc:
            raise Exception(f"URL Error: {exc}") from exc

    async def _nf_create_urllib(self, token: str, payload: dict, sentinel_token: str,
                                proxy_url: Optional[str], token_id: Optional[int] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/nf/create"
        user_agent = random.choice(MOBILE_USER_AGENTS)

        headers = {
            "Authorization": f"Bearer {token}",
            "openai-sentinel-token": sentinel_token,
            "Content-Type": "application/json",
            "User-Agent": user_agent,
            "Origin": "https://sora.chatgpt.com",
            "Referer": "https://sora.chatgpt.com/",
        }

        try:
            result = await asyncio.to_thread(
                self._post_json_sync, url, headers, payload, 30, proxy_url
            )
            return result
        except Exception as e:
            debug_logger.log_error(
                error_message=f"nf/create request failed: {str(e)}",
                status_code=0,
                response_text=str(e)
            )
            raise

    async def _generate_sentinel_token(self, token: Optional[str] = None) -> str:
        """Generate openai-sentinel-token by calling /backend-api/sentinel/req and solving PoW"""
        req_id = str(uuid4())
        user_agent = random.choice(DESKTOP_USER_AGENTS)
        pow_token = self._get_pow_token(user_agent)

        proxy_url = await self.proxy_manager.get_proxy_url()

        # Request sentinel/req endpoint
        url = f"{self.CHATGPT_BASE_URL}/backend-api/sentinel/req"
        payload = {"p": pow_token, "flow": self.SENTINEL_FLOW, "id": req_id}
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://sora.chatgpt.com",
            "Referer": "https://sora.chatgpt.com/",
            "User-Agent": user_agent,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            resp = await asyncio.to_thread(
                self._post_json_sync, url, headers, payload, 10, proxy_url
            )
        except Exception as e:
            debug_logger.log_error(
                error_message=f"Sentinel request failed: {str(e)}",
                status_code=0,
                response_text=str(e)
            )
            raise

        # Build final sentinel token
        sentinel_token = self._build_sentinel_token(
            self.SENTINEL_FLOW, req_id, pow_token, resp, user_agent
        )
        return sentinel_token

    @staticmethod
    def is_storyboard_prompt(prompt: str) -> bool:
        """检测提示词是否为分镜模式格式

        格式: [time]prompt 或 [time]prompt\n[time]prompt
        例如: [5.0s]猫猫从飞机上跳伞 [5.0s]猫猫降落

        Args:
            prompt: 用户输入的提示词

        Returns:
            True if prompt matches storyboard format
        """
        if not prompt:
            return False
        # 匹配格式: [数字s] 或 [数字.数字s]
        pattern = r'\[\d+(?:\.\d+)?s\]'
        matches = re.findall(pattern, prompt)
        # 至少包含一个时间标记才认为是分镜模式
        return len(matches) >= 1

    @staticmethod
    def format_storyboard_prompt(prompt: str) -> str:
        """将分镜格式提示词转换为API所需格式

        输入: 猫猫的奇妙冒险\n[5.0s]猫猫从飞机上跳伞 [5.0s]猫猫降落
        输出: current timeline:\nShot 1:...\n\ninstructions:\n猫猫的奇妙冒险

        Args:
            prompt: 原始分镜格式提示词

        Returns:
            格式化后的API提示词
        """
        # 匹配 [时间]内容 的模式
        pattern = r'\[(\d+(?:\.\d+)?)s\]\s*([^\[]+)'
        matches = re.findall(pattern, prompt)

        if not matches:
            return prompt

        # 提取总述(第一个[时间]之前的内容)
        first_bracket_pos = prompt.find('[')
        instructions = ""
        if first_bracket_pos > 0:
            instructions = prompt[:first_bracket_pos].strip()

        # 格式化分镜
        formatted_shots = []
        for idx, (duration, scene) in enumerate(matches, 1):
            scene = scene.strip()
            shot = f"Shot {idx}:\nduration: {duration}sec\nScene: {scene}"
            formatted_shots.append(shot)

        timeline = "\n\n".join(formatted_shots)

        # 如果有总述,添加instructions部分
        if instructions:
            return f"current timeline:\n{timeline}\n\ninstructions:\n{instructions}"
        else:
            return timeline

    async def _make_request(self, method: str, endpoint: str, token: str,
                           json_data: Optional[Dict] = None,
                           multipart: Optional[Dict] = None,
                           add_sentinel_token: bool = False,
                           token_id: Optional[int] = None) -> Dict[str, Any]:
        """Make HTTP request with proxy support

        Args:
            method: HTTP method (GET/POST)
            endpoint: API endpoint
            token: Access token
            json_data: JSON request body
            multipart: Multipart form data (for file uploads)
            add_sentinel_token: Whether to add openai-sentinel-token header (only for generation requests)
            token_id: Token ID for getting token-specific proxy (optional)
        """
        proxy_url = await self.proxy_manager.get_proxy_url(token_id)

        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent" : "Sora/1.2026.007 (Android 15; 24122RKC7C; build 2600700)"
        }

        # 添加 device_id cookie (oai-did) 以模拟真实的浏览器会话
        if token_id and self.db:
            try:
                token_obj = await self.db.get_token(token_id)
                if token_obj and token_obj.device_id:
                    # Add device_id as cookie
                    if "cookie" in headers:
                        headers["cookie"] += f"; oai-did={token_obj.device_id}"
                    else:
                        headers["cookie"] = f"oai-did={token_obj.device_id}"
            except Exception as e:
                # If getting device_id fails, continue without it
                debug_logger.log_info(f"Failed to get device_id for token {token_id}: {e}")

        # 只在生成请求时添加 sentinel token
        if add_sentinel_token:
            headers["openai-sentinel-token"] = await self._generate_sentinel_token(token)

        if not multipart:
            headers["Content-Type"] = "application/json"

        async with AsyncSession() as session:
            url = f"{self.base_url}{endpoint}"

            kwargs = {
                "headers": headers,
                "timeout": self.timeout,
                "impersonate": config.impersonate_browser  # 自动生成 User-Agent 和浏览器指纹
            }

            if proxy_url:
                kwargs["proxy"] = proxy_url

            if json_data:
                kwargs["json"] = json_data

            if multipart:
                kwargs["multipart"] = multipart

            # Log request
            debug_logger.log_request(
                method=method,
                url=url,
                headers=headers,
                body=json_data,
                files=multipart,
                proxy=proxy_url
            )

            # Record start time
            start_time = time.time()

            # Make request
            if method == "GET":
                response = await session.get(url, **kwargs)
            elif method == "POST":
                response = await session.post(url, **kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Parse response with comprehensive error handling
            response_json = None
            response_text = None
            
            # Try to parse JSON response
            try:
                response_json = response.json()
            except Exception as json_err:
                json_err_str = str(json_err)
                # Check if it's an IncompleteRead error (may come from curl_cffi internals)
                if "IncompleteRead" in json_err_str:
                    debug_logger.log_error(
                        error_message=f"IncompleteRead occurred while parsing JSON: {json_err_str}",
                        status_code=response.status_code,
                        response_text=json_err_str
                    )
                    raise Exception(f"IncompleteRead: {json_err_str}")
                # For other JSON errors, try to get text response
                try:
                    response_text = response.text
                except Exception as text_err:
                    text_err_str = str(text_err)
                    if "IncompleteRead" in text_err_str:
                        debug_logger.log_error(
                            error_message=f"IncompleteRead occurred while reading response text: {text_err_str}",
                            status_code=response.status_code,
                            response_text=text_err_str
                        )
                        raise Exception(f"IncompleteRead: {text_err_str}")
                    response_text = None
                response_json = None

            # Get response text if not already obtained
            if response_text is None:
                try:
                    response_text = response.text
                except Exception as text_err:
                    text_err_str = str(text_err)
                    if "IncompleteRead" in text_err_str:
                        debug_logger.log_error(
                            error_message=f"IncompleteRead occurred while reading response text: {text_err_str}",
                            status_code=response.status_code,
                            response_text=text_err_str
                        )
                        raise Exception(f"IncompleteRead: {text_err_str}")
                    response_text = None

            # Log response
            debug_logger.log_response(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=response_json if response_json else response_text,
                duration_ms=duration_ms
            )

            # Check status
            if response.status_code not in [200, 201]:
                # Parse error response
                error_data = None
                try:
                    if response_json:
                        error_data = response_json
                    else:
                        error_data = response.json()
                except Exception as err_err:
                    err_err_str = str(err_err)
                    if "IncompleteRead" in err_err_str:
                        debug_logger.log_error(
                            error_message=f"IncompleteRead occurred while parsing error response: {err_err_str}",
                            status_code=response.status_code,
                            response_text=err_err_str
                        )
                        raise Exception(f"IncompleteRead: {err_err_str}")
                    pass

                # Check for 403 Forbidden or 429 Rate Limit - log for potential captcha solving
                if (response.status_code == 403 or response.status_code == 429) and self.db:
                    try:
                        captcha_config = await self.db.get_captcha_config()
                        if captcha_config.captcha_method == "yescaptcha" and captcha_config.yescaptcha_api_key:
                            # Check if this is a Cloudflare challenge or rate limit that might need captcha
                            is_cf_challenge = False
                            is_rate_limit = False
                            
                            if error_data and isinstance(error_data, dict):
                                error_info = error_data.get("error", {})
                                error_code = error_info.get("code", "")
                                error_msg = str(error_data).lower()
                                
                                # Check for Cloudflare challenge indicators
                                if error_code == "cf_shield_429" or "cloudflare" in error_msg or "cf_" in error_code:
                                    is_cf_challenge = True
                                
                                # Check for rate limit that might need captcha (not too_many_concurrent_tasks)
                                if response.status_code == 429 and error_code != "too_many_concurrent_tasks":
                                    is_rate_limit = True
                            
                            if is_cf_challenge or (response.status_code == 429 and is_rate_limit):
                                debug_logger.log_info(f"{response.status_code} error detected on {url}, YesCaptcha is configured but site key extraction needed for full implementation")
                                # Note: Full reCAPTCHA solving requires extracting site key from HTML response
                                # This would require parsing the response body to find the reCAPTCHA site key
                            elif response.status_code == 429:
                                # too_many_concurrent_tasks - this is a business logic error, not a captcha issue
                                debug_logger.log_info(f"429 error detected: {error_data.get('error', {}).get('code', 'unknown')} - This is a business logic error, not a captcha issue")
                    except Exception as captcha_error:
                        debug_logger.log_error(
                            error_message=f"Captcha config check failed: {str(captcha_error)}",
                            status_code=500,
                            response_text=str(captcha_error)
                        )

                # Check for structured errors (unsupported_country_code, heavy_load, etc.)
                if error_data and isinstance(error_data, dict):
                    error_info = error_data.get("error", {})
                    error_code = error_info.get("code", "")
                    
                    # Check for unsupported_country_code error
                    if error_code == "unsupported_country_code":
                        # Create structured error with full error data
                        import json
                        error_msg = json.dumps(error_data)
                        debug_logger.log_error(
                            error_message=f"Unsupported country: {error_msg}",
                            status_code=response.status_code,
                            response_text=error_msg
                        )
                        # Raise exception with structured error data
                        raise Exception(error_msg)
                    
                    # Check for heavy_load error - pass through as structured error
                    if error_code == "heavy_load":
                        import json
                        error_msg = json.dumps(error_data)
                        debug_logger.log_error(
                            error_message=f"Heavy load detected: {error_msg}",
                            status_code=response.status_code,
                            response_text=error_msg
                        )
                        # Raise exception with structured error data for frontend retry
                        raise Exception(error_msg)

                # Generic error handling
                error_text = response_text if response_text else "Unknown error"
                error_msg = f"API request failed: {response.status_code} - {error_text}"
                debug_logger.log_error(
                    error_message=error_msg,
                    status_code=response.status_code,
                    response_text=error_text
                )
                raise Exception(error_msg)

            # Return parsed JSON or try to parse again
            if response_json:
                return response_json
            else:
                try:
                    return response.json()
                except Exception as final_err:
                    final_err_str = str(final_err)
                    if "IncompleteRead" in final_err_str:
                        debug_logger.log_error(
                            error_message=f"IncompleteRead occurred while parsing final response: {final_err_str}",
                            status_code=response.status_code,
                            response_text=final_err_str
                        )
                        raise Exception(f"IncompleteRead: {final_err_str}")
                    raise Exception(f"Failed to parse response: {final_err_str}")
    
    async def get_user_info(self, token: str) -> Dict[str, Any]:
        """Get user information"""
        return await self._make_request("GET", "/me", token)
    
    async def upload_image(self, image_data: bytes, token: str, filename: str = "image.png", token_id: Optional[int] = None) -> str:
        """Upload image and return media_id

        使用 CurlMime 对象上传文件（curl_cffi 的正确方式）
        参考：https://curl-cffi.readthedocs.io/en/latest/quick_start.html#uploads
        
        Args:
            image_data: Image data as bytes
            token: Access token
            filename: Image filename
            token_id: Token ID for getting token-specific proxy (optional)
        """
        # 检测图片类型
        mime_type = "image/png"
        if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
            mime_type = "image/jpeg"
        elif filename.lower().endswith('.webp'):
            mime_type = "image/webp"

        # 创建 CurlMime 对象
        mp = CurlMime()

        # 添加文件部分
        mp.addpart(
            name="file",
            content_type=mime_type,
            filename=filename,
            data=image_data
        )

        # 添加文件名字段
        mp.addpart(
            name="file_name",
            data=filename.encode('utf-8')
        )

        # Retry logic for TLS/OpenSSL errors (common on Windows)
        max_retries = 5
        retry_delay = 3  # Start with 3 seconds
        
        for attempt in range(max_retries):
            try:
                result = await self._make_request("POST", "/uploads", token, multipart=mp, token_id=token_id)
                return result["id"]
            except Exception as e:
                error_msg = str(e)
                is_tls_error = ("TLS" in error_msg or "curl" in error_msg or "OPENSSL" in error_msg or 
                               "error:00000000" in error_msg or "invalid library" in error_msg)
                
                if is_tls_error and attempt < max_retries - 1:
                    # Exponential backoff for TLS errors
                    wait_time = retry_delay * (2 ** attempt)
                    debug_logger.log_info(
                        f"TLS/OpenSSL error during image upload (attempt {attempt + 1}/{max_retries}): {error_msg[:200]}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Re-raise if not TLS error or last attempt
                    debug_logger.log_error(
                        error_message=f"Image upload failed: {error_msg}",
                        status_code=500,
                        response_text=error_msg
                    )
                    raise Exception(f"Failed to upload image: {error_msg}")
        
        # Should not reach here, but just in case
        raise Exception("Image upload failed after all retries")
    
    async def generate_image(self, prompt: str, token: str, width: int = 360,
                            height: int = 360, media_id: Optional[str] = None, token_id: Optional[int] = None) -> str:
        """Generate image (text-to-image or image-to-image)"""
        operation = "remix" if media_id else "simple_compose"

        inpaint_items = []
        if media_id:
            inpaint_items = [{
                "type": "image",
                "frame_index": 0,
                "upload_media_id": media_id
            }]

        json_data = {
            "type": "image_gen",
            "operation": operation,
            "prompt": prompt,
            "width": width,
            "height": height,
            "n_variants": 1,
            "n_frames": 1,
            "inpaint_items": inpaint_items
        }

        # 生成请求需要添加 sentinel token
        result = await self._make_request("POST", "/video_gen", token, json_data=json_data, add_sentinel_token=True, token_id=token_id)
        return result["id"]
    
    async def generate_video(self, prompt: str, token: str, orientation: str = "landscape",
                            media_id: Optional[str] = None, n_frames: int = 450, style_id: Optional[str] = None,
                            model: str = "sy_8", size: str = "small", token_id: Optional[int] = None) -> str:
        """Generate video (text-to-video or image-to-video)

        Args:
            prompt: Video generation prompt
            token: Access token
            orientation: Video orientation (landscape/portrait)
            media_id: Optional image media_id for image-to-video
            n_frames: Number of frames (300/450/750)
            style_id: Optional style ID
            model: Model to use (sy_8 for standard, sy_ore for pro)
            size: Video size (small for standard, large for HD)
            token_id: Token ID for getting token-specific proxy (optional)
        """
        inpaint_items = []
        if media_id:
            inpaint_items = [{
                "kind": "upload",
                "upload_id": media_id
            }]

        json_data = {
            "kind": "video",
            "prompt": prompt,
            "orientation": orientation,
            "size": size,
            "n_frames": n_frames,
            "model": model,
            "inpaint_items": inpaint_items,
            "style_id": style_id
        }

        # 生成请求需要添加 sentinel token
        proxy_url = await self.proxy_manager.get_proxy_url(token_id)
        sentinel_token = await self._generate_sentinel_token(token)
        result = await self._nf_create_urllib(token, json_data, sentinel_token, proxy_url, token_id)
        return result["id"]
    
    async def get_image_tasks(self, token: str, limit: int = 20, token_id: Optional[int] = None) -> Dict[str, Any]:
        """Get recent image generation tasks"""
        return await self._make_request("GET", f"/v2/recent_tasks?limit={limit}", token, token_id=token_id)

    async def get_video_drafts(self, token: str, limit: int = 15, token_id: Optional[int] = None) -> Dict[str, Any]:
        """Get recent video drafts"""
        return await self._make_request("GET", f"/project_y/profile/drafts?limit={limit}", token, token_id=token_id)

    async def get_pending_tasks(self, token: str, token_id: Optional[int] = None) -> list:
        """Get pending video generation tasks

        Returns:
            List of pending tasks with progress information
        """
        result = await self._make_request("GET", "/nf/pending/v2", token, token_id=token_id)
        # The API returns a list directly
        return result if isinstance(result, list) else []

    async def post_video_for_watermark_free(self, generation_id: str, prompt: str, token: str) -> str:
        """Post video to get watermark-free version

        Args:
            generation_id: The generation ID (e.g., gen_01k9btrqrnen792yvt703dp0tq)
            prompt: The original generation prompt
            token: Access token

        Returns:
            Post ID (e.g., s_690ce161c2488191a3476e9969911522)
        """
        json_data = {
            "attachments_to_create": [
                {
                    "generation_id": generation_id,
                    "kind": "sora"
                }
            ],
            "post_text": ""
        }

        # 发布请求需要添加 sentinel token
        result = await self._make_request("POST", "/project_y/post", token, json_data=json_data, add_sentinel_token=True)

        # 返回 post.id
        return result.get("post", {}).get("id", "")

    async def delete_post(self, post_id: str, token: str) -> bool:
        """Delete a published post

        Args:
            post_id: The post ID (e.g., s_690ce161c2488191a3476e9969911522)
            token: Access token

        Returns:
            True if deletion was successful
        """
        proxy_url = await self.proxy_manager.get_proxy_url()

        headers = {
            "Authorization": f"Bearer {token}"
        }

        async with AsyncSession() as session:
            url = f"{self.base_url}/project_y/post/{post_id}"

            kwargs = {
                "headers": headers,
                "timeout": self.timeout,
                "impersonate": config.impersonate_browser
            }

            if proxy_url:
                kwargs["proxy"] = proxy_url

            # Log request
            debug_logger.log_request(
                method="DELETE",
                url=url,
                headers=headers,
                body=None,
                files=None,
                proxy=proxy_url
            )

            # Record start time
            start_time = time.time()

            # Make DELETE request
            response = await session.delete(url, **kwargs)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log response
            debug_logger.log_response(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=response.text if response.text else "No content",
                duration_ms=duration_ms
            )

            # Check status (DELETE typically returns 204 No Content or 200 OK)
            if response.status_code not in [200, 204]:
                error_msg = f"Delete post failed: {response.status_code} - {response.text}"
                debug_logger.log_error(
                    error_message=error_msg,
                    status_code=response.status_code,
                    response_text=response.text
                )
                raise Exception(error_msg)

            return True

    async def get_watermark_free_url_builtin(self, post_id: str, token: Optional[str] = None, token_id: Optional[int] = None) -> str:
        """Get watermark-free video URL by parsing Sora share page directly (built-in, no external server needed)

        Args:
            post_id: Post ID to parse (e.g., s_690c0f574c3881918c3bc5b682a7e9fd)
            token: Access token (optional, for authenticated requests)
            token_id: Token ID for getting token-specific proxy (optional)

        Returns:
            Download link (watermark-free video URL)

        Raises:
            Exception: If parse fails
        """
        proxy_url = await self.proxy_manager.get_proxy_url(token_id)

        # Construct the share URL
        share_url = f"https://sora.chatgpt.com/p/{post_id}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

        # Add authorization if token provided
        if token:
            headers["Authorization"] = f"Bearer {token}"

        kwargs = {
            "headers": headers,
            "timeout": 30,
            "impersonate": "chrome"
        }

        if proxy_url:
            kwargs["proxy"] = proxy_url

        try:
            async with AsyncSession() as session:
                # Record start time
                start_time = time.time()

                # Make GET request to Sora share page
                debug_logger.log_info(f"Fetching Sora share page: {share_url}")
                response = await session.get(share_url, **kwargs)

                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Log response
                debug_logger.log_response(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=f"HTML content ({len(response.text) if response.text else 0} bytes)",
                    duration_ms=duration_ms
                )

                # Check status
                if response.status_code != 200:
                    error_msg = f"Failed to fetch share page: {response.status_code} - {response.text[:500] if response.text else 'No content'}"
                    debug_logger.log_error(
                        error_message=error_msg,
                        status_code=response.status_code,
                        response_text=response.text[:1000] if response.text else "No content"
                    )
                    raise Exception(error_msg)

                # Parse HTML to extract video URL
                html_content = response.text
                if not html_content:
                    raise Exception("Empty response from share page")

                # Try multiple patterns to find video URL
                # Pattern 1: Look for video URLs in JSON data embedded in HTML
                # Pattern 2: Look for direct video URLs in script tags
                # Pattern 3: Look for video URLs in data attributes

                download_link = None

                # Pattern 1: Extract from __NEXT_DATA__ or similar JSON structures
                json_data_pattern = r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>'
                json_match = re.search(json_data_pattern, html_content, re.DOTALL)
                if json_match:
                    try:
                        import json
                        json_data = json.loads(json_match.group(1))
                        # Navigate through the JSON structure to find video URL
                        # This structure may vary, so we try multiple paths
                        def find_video_url(obj, path=""):
                            if isinstance(obj, dict):
                                for key, value in obj.items():
                                    if key in ["url", "video_url", "download_url", "downloadable_url", "source_url"]:
                                        if isinstance(value, str) and value.startswith("http"):
                                            return value
                                    if isinstance(value, (dict, list)):
                                        result = find_video_url(value, f"{path}.{key}")
                                        if result:
                                            return result
                            elif isinstance(obj, list):
                                for i, item in enumerate(obj):
                                    result = find_video_url(item, f"{path}[{i}]")
                                    if result:
                                        return result
                            return None

                        download_link = find_video_url(json_data)
                    except Exception as json_err:
                        debug_logger.log_info(f"Failed to parse JSON data: {str(json_err)}")

                # Pattern 2: Look for video URLs in script tags with specific patterns
                if not download_link:
                    # Look for patterns like: "url":"https://..." or "video_url":"https://..."
                    url_patterns = [
                        r'"(?:url|video_url|download_url|downloadable_url|source_url)"\s*:\s*"([^"]+)"',
                        r'<video[^>]+src=["\']([^"\']+)["\']',
                        r'https?://[^"\s<>]+\.(?:mp4|mov|m4v|webm)(?:\?[^"\s<>]*)?'
                    ]
                    for pattern in url_patterns:
                        matches = re.findall(pattern, html_content, re.IGNORECASE)
                        for match in matches:
                            if isinstance(match, tuple):
                                match = match[0] if match else None
                            if match and match.startswith("http") and "video" in match.lower():
                                download_link = match
                                break
                        if download_link:
                            break

                # Pattern 3: Look for video URLs in data attributes or meta tags
                if not download_link:
                    meta_patterns = [
                        r'<meta[^>]+property=["\']og:video["\'][^>]+content=["\']([^"\']+)["\']',
                        r'<meta[^>]+name=["\']video:url["\'][^>]+content=["\']([^"\']+)["\']',
                        r'data-video-url=["\']([^"\']+)["\']',
                        r'data-url=["\']([^"\']+)["\']'
                    ]
                    for pattern in meta_patterns:
                        match = re.search(pattern, html_content, re.IGNORECASE)
                        if match:
                            url = match.group(1) if isinstance(match.groups(), tuple) and match.groups() else match.group(0)
                            if url and url.startswith("http"):
                                download_link = url
                                break

                if not download_link:
                    # Last resort: try to find any video URL in the HTML
                    video_url_pattern = r'https?://[^"\s<>]+\.(?:mp4|mov|m4v|webm)(?:\?[^"\s<>]*)?'
                    matches = re.findall(video_url_pattern, html_content, re.IGNORECASE)
                    if matches:
                        download_link = matches[0]

                if not download_link:
                    # Log HTML snippet for debugging
                    html_snippet = html_content[:2000] if len(html_content) > 2000 else html_content
                    debug_logger.log_error(
                        error_message=f"Could not find video URL in share page HTML",
                        status_code=404,
                        response_text=html_snippet
                    )
                    raise Exception("Could not find video URL in share page. The page structure may have changed.")

                debug_logger.log_info(f"Built-in parse successful: {download_link}")
                return download_link

        except Exception as e:
            debug_logger.log_error(
                error_message=f"Built-in parse request failed: {str(e)}",
                status_code=500,
                response_text=str(e)
            )
            raise

    async def get_watermark_free_url_sora_downloader(self, parse_url: str, parse_token: str, post_id: str) -> str:
        """Get watermark-free video URL from sora-downloader server (external server)

        Args:
            parse_url: sora-downloader server URL (e.g., http://localhost:5000)
            parse_token: Access token for sora-downloader (APP_ACCESS_TOKEN, optional)
            post_id: Post ID to parse (e.g., s_690c0f574c3881918c3bc5b682a7e9fd)

        Returns:
            Download link from sora-downloader server

        Raises:
            Exception: If parse fails or token is invalid
        """
        proxy_url = await self.proxy_manager.get_proxy_url()

        # Construct the share URL
        share_url = f"https://sora.chatgpt.com/p/{post_id}"

        # Prepare request - sora-downloader uses root endpoint
        json_data = {
            "url": share_url
        }

        # Add token if provided (APP_ACCESS_TOKEN)
        if parse_token:
            json_data["token"] = parse_token

        kwargs = {
            "json": json_data,
            "timeout": 30,
            "impersonate": "chrome"
        }

        if proxy_url:
            kwargs["proxy"] = proxy_url

        try:
            async with AsyncSession() as session:
                # Record start time
                start_time = time.time()

                # Make POST request to sora-downloader (root endpoint)
                # Remove trailing slash if present
                base_url = parse_url.rstrip('/')
                response = await session.post(base_url, **kwargs)

                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Log response
                debug_logger.log_response(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=response.text if response.text else "No content",
                    duration_ms=duration_ms
                )

                # Check status
                if response.status_code != 200:
                    error_msg = f"Sora-downloader parse failed: {response.status_code} - {response.text}"
                    debug_logger.log_error(
                        error_message=error_msg,
                        status_code=response.status_code,
                        response_text=response.text
                    )
                    raise Exception(error_msg)

                # Parse response
                result = response.json()

                # Check for error in response
                if "error" in result:
                    error_msg = f"Sora-downloader parse error: {result['error']}"
                    debug_logger.log_error(
                        error_message=error_msg,
                        status_code=401,
                        response_text=str(result)
                    )
                    raise Exception(error_msg)

                # Extract download link - sora-downloader returns "download_link" or "url"
                download_link = result.get("download_link") or result.get("url")
                if not download_link:
                    raise Exception("No download_link or url in sora-downloader response")

                debug_logger.log_info(f"Sora-downloader parse successful: {download_link}")
                return download_link

        except Exception as e:
            debug_logger.log_error(
                error_message=f"Sora-downloader parse request failed: {str(e)}",
                status_code=500,
                response_text=str(e)
            )
            raise

    async def get_watermark_free_url_custom(self, parse_url: str, parse_token: str, post_id: str) -> str:
        """Get watermark-free video URL from custom parse server

        Args:
            parse_url: Custom parse server URL (e.g., http://example.com)
            parse_token: Access token for custom parse server
            post_id: Post ID to parse (e.g., s_690c0f574c3881918c3bc5b682a7e9fd)

        Returns:
            Download link from custom parse server

        Raises:
            Exception: If parse fails or token is invalid
        """
        proxy_url = await self.proxy_manager.get_proxy_url()

        # Construct the share URL
        share_url = f"https://sora.chatgpt.com/p/{post_id}"

        # Prepare request
        json_data = {
            "url": share_url,
            "token": parse_token
        }

        kwargs = {
            "json": json_data,
            "timeout": 30,
            "impersonate": "chrome"
        }

        if proxy_url:
            kwargs["proxy"] = proxy_url

        try:
            async with AsyncSession() as session:
                # Record start time
                start_time = time.time()

                # Make POST request to custom parse server
                response = await session.post(f"{parse_url}/get-sora-link", **kwargs)

                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Log response
                debug_logger.log_response(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=response.text if response.text else "No content",
                    duration_ms=duration_ms
                )

                # Check status
                if response.status_code != 200:
                    error_msg = f"Custom parse failed: {response.status_code} - {response.text}"
                    debug_logger.log_error(
                        error_message=error_msg,
                        status_code=response.status_code,
                        response_text=response.text
                    )
                    raise Exception(error_msg)

                # Parse response
                result = response.json()

                # Check for error in response
                if "error" in result:
                    error_msg = f"Custom parse error: {result['error']}"
                    debug_logger.log_error(
                        error_message=error_msg,
                        status_code=401,
                        response_text=str(result)
                    )
                    raise Exception(error_msg)

                # Extract download link
                download_link = result.get("download_link")
                if not download_link:
                    raise Exception("No download_link in custom parse response")

                debug_logger.log_info(f"Custom parse successful: {download_link}")
                return download_link

        except Exception as e:
            debug_logger.log_error(
                error_message=f"Custom parse request failed: {str(e)}",
                status_code=500,
                response_text=str(e)
            )
            raise

    # ==================== Character Creation Methods ====================

    async def upload_character_video(self, video_data: bytes, token: str) -> str:
        """Upload character video and return cameo_id

        Args:
            video_data: Video file bytes
            token: Access token

        Returns:
            cameo_id
        """
        mp = CurlMime()
        mp.addpart(
            name="file",
            content_type="video/mp4",
            filename="video.mp4",
            data=video_data
        )
        mp.addpart(
            name="timestamps",
            data=b"0,3"
        )

        result = await self._make_request("POST", "/characters/upload", token, multipart=mp)
        return result.get("id")

    async def get_cameo_status(self, cameo_id: str, token: str) -> Dict[str, Any]:
        """Get character (cameo) processing status

        Args:
            cameo_id: The cameo ID returned from upload_character_video
            token: Access token

        Returns:
            Dictionary with status, display_name_hint, username_hint, profile_asset_url, instruction_set_hint
        """
        return await self._make_request("GET", f"/project_y/cameos/in_progress/{cameo_id}", token)

    async def download_character_image(self, image_url: str) -> bytes:
        """Download character image from URL

        Args:
            image_url: The profile_asset_url from cameo status

        Returns:
            Image file bytes
        """
        proxy_url = await self.proxy_manager.get_proxy_url()

        kwargs = {
            "timeout": self.timeout,
            "impersonate": "chrome"
        }

        if proxy_url:
            kwargs["proxy"] = proxy_url

        async with AsyncSession() as session:
            response = await session.get(image_url, **kwargs)
            if response.status_code != 200:
                raise Exception(f"Failed to download image: {response.status_code}")
            return response.content

    async def finalize_character(self, cameo_id: str, username: str, display_name: str,
                                profile_asset_pointer: str, instruction_set, token: str) -> str:
        """Finalize character creation

        Args:
            cameo_id: The cameo ID
            username: Character username
            display_name: Character display name
            profile_asset_pointer: Asset pointer from upload_character_image
            instruction_set: Character instruction set (not used by API, always set to None)
            token: Access token

        Returns:
            character_id
        """
        # Note: API always expects instruction_set to be null
        # The instruction_set parameter is kept for backward compatibility but not used
        _ = instruction_set  # Suppress unused parameter warning
        json_data = {
            "cameo_id": cameo_id,
            "username": username,
            "display_name": display_name,
            "profile_asset_pointer": profile_asset_pointer,
            "instruction_set": None,
            "safety_instruction_set": None
        }

        result = await self._make_request("POST", "/characters/finalize", token, json_data=json_data)
        return result.get("character", {}).get("character_id")

    async def set_character_public(self, cameo_id: str, token: str) -> bool:
        """Set character as public

        Args:
            cameo_id: The cameo ID
            token: Access token

        Returns:
            True if successful
        """
        json_data = {"visibility": "public"}
        await self._make_request("POST", f"/project_y/cameos/by_id/{cameo_id}/update_v2", token, json_data=json_data)
        return True

    async def upload_character_image(self, image_data: bytes, token: str, token_id: Optional[int] = None) -> str:
        """Upload character image and return asset_pointer

        Args:
            image_data: Image file bytes
            token: Access token
            token_id: Token ID for getting token-specific proxy (optional)

        Returns:
            asset_pointer
        """
        mp = CurlMime()
        mp.addpart(
            name="file",
            content_type="image/webp",
            filename="profile.webp",
            data=image_data
        )
        mp.addpart(
            name="use_case",
            data=b"profile"
        )

        # Retry logic for TLS/OpenSSL errors (common on Windows)
        max_retries = 5
        retry_delay = 3  # Start with 3 seconds
        
        for attempt in range(max_retries):
            try:
                result = await self._make_request("POST", "/project_y/file/upload", token, multipart=mp, token_id=token_id)
                return result.get("asset_pointer")
            except Exception as e:
                error_msg = str(e)
                is_tls_error = ("TLS" in error_msg or "curl" in error_msg or "OPENSSL" in error_msg or 
                               "error:00000000" in error_msg or "invalid library" in error_msg)
                
                if is_tls_error and attempt < max_retries - 1:
                    # Exponential backoff for TLS errors
                    wait_time = retry_delay * (2 ** attempt)
                    debug_logger.log_info(
                        f"TLS/OpenSSL error during character image upload (attempt {attempt + 1}/{max_retries}): {error_msg[:200]}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Re-raise if not TLS error or last attempt
                    debug_logger.log_error(
                        error_message=f"Character image upload failed: {error_msg}",
                        status_code=500,
                        response_text=error_msg
                    )
                    raise Exception(f"Failed to upload character image: {error_msg}")
        
        # Should not reach here, but just in case
        raise Exception("Character image upload failed after all retries")

    async def delete_character(self, character_id: str, token: str) -> bool:
        """Delete a character

        Args:
            character_id: The character ID
            token: Access token

        Returns:
            True if successful
        """
        proxy_url = await self.proxy_manager.get_proxy_url()

        headers = {
            "Authorization": f"Bearer {token}"
        }

        async with AsyncSession() as session:
            url = f"{self.base_url}/project_y/characters/{character_id}"

            kwargs = {
                "headers": headers,
                "timeout": self.timeout,
                "impersonate": config.impersonate_browser
            }

            if proxy_url:
                kwargs["proxy"] = proxy_url

            response = await session.delete(url, **kwargs)
            if response.status_code not in [200, 204]:
                raise Exception(f"Failed to delete character: {response.status_code}")
            return True

    async def remix_video(self, remix_target_id: str, prompt: str, token: str,
                         orientation: str = "portrait", n_frames: int = 450, style_id: Optional[str] = None) -> str:
        """Generate video using remix (based on existing video)

        Args:
            remix_target_id: The video ID from Sora share link (e.g., s_690d100857248191b679e6de12db840e)
            prompt: Generation prompt
            token: Access token
            orientation: Video orientation (portrait/landscape)
            n_frames: Number of frames
            style_id: Optional style ID

        Returns:
            task_id
        """
        json_data = {
            "kind": "video",
            "prompt": prompt,
            "inpaint_items": [],
            "remix_target_id": remix_target_id,
            "cameo_ids": [],
            "cameo_replacements": {},
            "model": "sy_8",
            "orientation": orientation,
            "n_frames": n_frames,
            "style_id": style_id
        }

        # Generate sentinel token and call /nf/create using urllib
        proxy_url = await self.proxy_manager.get_proxy_url()
        sentinel_token = await self._generate_sentinel_token(token)
        result = await self._nf_create_urllib(token, json_data, sentinel_token, proxy_url)
        return result.get("id")

    async def generate_storyboard(self, prompt: str, token: str, orientation: str = "landscape",
                                 media_id: Optional[str] = None, n_frames: int = 450, style_id: Optional[str] = None) -> str:
        """Generate video using storyboard mode

        Args:
            prompt: Formatted storyboard prompt (Shot 1:\nduration: 5.0sec\nScene: ...)
            token: Access token
            orientation: Video orientation (portrait/landscape)
            media_id: Optional image media_id for image-to-video
            n_frames: Number of frames
            style_id: Optional style ID

        Returns:
            task_id
        """
        inpaint_items = []
        if media_id:
            inpaint_items = [{
                "kind": "upload",
                "upload_id": media_id
            }]

        json_data = {
            "kind": "video",
            "prompt": prompt,
            "title": "Draft your video",
            "orientation": orientation,
            "size": "small",
            "n_frames": n_frames,
            "storyboard_id": None,
            "inpaint_items": inpaint_items,
            "remix_target_id": None,
            "model": "sy_8",
            "metadata": None,
            "style_id": style_id,
            "cameo_ids": None,
            "cameo_replacements": None,
            "audio_caption": None,
            "audio_transcript": None,
            "video_caption": None
        }

        result = await self._make_request("POST", "/nf/create/storyboard", token, json_data=json_data, add_sentinel_token=True)
        return result.get("id")

    async def enhance_prompt(self, prompt: str, token: str, expansion_level: str = "medium",
                            duration_s: int = 10, token_id: Optional[int] = None) -> str:
        """Enhance prompt using Sora's prompt enhancement API

        Args:
            prompt: Original prompt to enhance
            token: Access token
            expansion_level: Expansion level (medium/long)
            duration_s: Duration in seconds (10/15/20)
            token_id: Token ID for getting token-specific proxy (optional)

        Returns:
            Enhanced prompt text
        """
        json_data = {
            "prompt": prompt,
            "expansion_level": expansion_level,
            "duration_s": duration_s
        }

        result = await self._make_request("POST", "/editor/enhance_prompt", token, json_data=json_data, token_id=token_id)
        return result.get("enhanced_prompt", "")
