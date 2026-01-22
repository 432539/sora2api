"""Captcha service for handling reCAPTCHA verification"""
import asyncio
import json
import time
from typing import Optional
from curl_cffi.requests import AsyncSession
from ..core.logger import debug_logger


class YesCaptchaService:
    """YesCaptcha service for solving reCAPTCHA"""
    
    def __init__(self, api_key: str, api_url: str = "https://api.yescaptcha.com"):
        """
        Initialize YesCaptcha service
        
        Args:
            api_key: YesCaptcha API key
            api_url: YesCaptcha API URL (default: https://api.yescaptcha.com)
        """
        self.api_key = api_key
        self.api_url = api_url.rstrip('/')
    
    async def solve_recaptcha_v2(self, site_key: str, page_url: str, proxy_url: Optional[str] = None) -> Optional[str]:
        """
        Solve reCAPTCHA v2 using YesCaptcha
        
        Args:
            site_key: reCAPTCHA site key
            page_url: Page URL where reCAPTCHA is located
            proxy_url: Optional proxy URL
            
        Returns:
            reCAPTCHA token if successful, None otherwise
        """
        if not self.api_key:
            debug_logger.log_error(
                error_message="YesCaptcha API key not configured",
                status_code=400,
                response_text=""
            )
            return None
        
        try:
            # Step 1: Create task
            create_task_url = f"{self.api_url}/createTask"
            create_payload = {
                "clientKey": self.api_key,
                "task": {
                    "type": "RecaptchaV2TaskProxyless",
                    "websiteURL": page_url,
                    "websiteKey": site_key
                }
            }
            
            if proxy_url:
                # Use proxy if provided
                create_payload["task"]["type"] = "RecaptchaV2Task"
                create_payload["task"]["proxyType"] = "http"
                create_payload["task"]["proxyAddress"] = proxy_url
            
            async with AsyncSession() as session:
                debug_logger.log_info(f"Creating YesCaptcha task for site_key: {site_key[:20]}...")
                create_response = await session.post(create_task_url, json=create_payload, timeout=30)
                
                if create_response.status_code != 200:
                    error_msg = f"YesCaptcha create task failed: {create_response.status_code} - {create_response.text}"
                    debug_logger.log_error(
                        error_message=error_msg,
                        status_code=create_response.status_code,
                        response_text=create_response.text
                    )
                    return None
                
                create_result = create_response.json()
                if create_result.get("errorId") != 0:
                    error_msg = f"YesCaptcha create task error: {create_result.get('errorDescription', 'Unknown error')}"
                    debug_logger.log_error(
                        error_message=error_msg,
                        status_code=400,
                        response_text=str(create_result)
                    )
                    return None
                
                task_id = create_result.get("taskId")
                if not task_id:
                    debug_logger.log_error(
                        error_message="YesCaptcha task ID not found in response",
                        status_code=400,
                        response_text=str(create_result)
                    )
                    return None
                
                debug_logger.log_info(f"YesCaptcha task created: {task_id}")
                
                # Step 2: Poll for result
                get_result_url = f"{self.api_url}/getTaskResult"
                max_attempts = 60  # Wait up to 5 minutes (60 * 5 seconds)
                attempt = 0
                
                while attempt < max_attempts:
                    await asyncio.sleep(5)  # Wait 5 seconds between polls
                    attempt += 1
                    
                    get_payload = {
                        "clientKey": self.api_key,
                        "taskId": task_id
                    }
                    
                    get_response = await session.post(get_result_url, json=get_payload, timeout=30)
                    
                    if get_response.status_code != 200:
                        debug_logger.log_error(
                            error_message=f"YesCaptcha get result failed: {get_response.status_code}",
                            status_code=get_response.status_code,
                            response_text=get_response.text
                        )
                        continue
                    
                    get_result = get_response.json()
                    
                    if get_result.get("errorId") != 0:
                        error_msg = f"YesCaptcha get result error: {get_result.get('errorDescription', 'Unknown error')}"
                        debug_logger.log_error(
                            error_message=error_msg,
                            status_code=400,
                            response_text=str(get_result)
                        )
                        return None
                    
                    status = get_result.get("status")
                    if status == "ready":
                        solution = get_result.get("solution", {})
                        token = solution.get("gRecaptchaResponse")
                        if token:
                            debug_logger.log_info(f"YesCaptcha solved successfully: {token[:50]}...")
                            return token
                        else:
                            debug_logger.log_error(
                                error_message="YesCaptcha solution token not found",
                                status_code=400,
                                response_text=str(get_result)
                            )
                            return None
                    elif status == "processing":
                        debug_logger.log_info(f"YesCaptcha task {task_id} still processing (attempt {attempt}/{max_attempts})")
                        continue
                    else:
                        error_msg = f"YesCaptcha task failed with status: {status}"
                        debug_logger.log_error(
                            error_message=error_msg,
                            status_code=400,
                            response_text=str(get_result)
                        )
                        return None
                
                # Timeout
                debug_logger.log_error(
                    error_message=f"YesCaptcha task timeout after {max_attempts} attempts",
                    status_code=408,
                    response_text=""
                )
                return None
                
        except Exception as e:
            debug_logger.log_error(
                error_message=f"YesCaptcha solve failed: {str(e)}",
                status_code=500,
                response_text=str(e)
            )
            return None
