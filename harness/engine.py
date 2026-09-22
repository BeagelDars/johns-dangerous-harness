"""
Core Agent Harness Engine
Handles API calls (OpenAI-compatible format), multi-turn tool loops, and circuit breakers.
"""
import os
import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Generator, Optional
from harness.registry import registry
from harness.server import ensure_server_running
import config

_CLOUD_EXHAUSTED = False
_CLOUD_EXHAUSTED_UNTIL = 0.0
_http_pool = None

def _get_http_pool():
    global _http_pool
    if _http_pool is None:
        try:
            import urllib3
            _http_pool = urllib3.PoolManager(
                num_pools=5,
                maxsize=10,
                timeout=urllib3.Timeout(connect=5.0, read=30.0),
                retries=False
            )
        except Exception:
            _http_pool = False
    return _http_pool

class AgentEngine:
    def __init__(
        self,
        base_url: str = config.BASE_URL,
        api_key: str = config.API_KEY,
        model: str = config.DEFAULT_MODEL,
        max_steps: int = config.MAX_STEPS,
        system_prompt: str = config.SYSTEM_PROMPT,
        temperature: float = config.TEMPERATURE
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_steps = max_steps
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.history: List[Dict[str, Any]] = []
        self.active_mode = config.DEFAULT_PROFILE

        # Apply profile settings
        if self.active_mode in config.PROFILES:
            prof = config.PROFILES[self.active_mode]
            self.model = prof["model"]
            self.base_url = prof["base_url"].rstrip("/")
            self.api_key = prof["api_key"]

        self.aborted = False
        self.pending_events: List[Dict[str, Any]] = []

        # If pointing to local Ollama, ensure it is silently running in background without blocking startup
        if "11434" in self.base_url and ("localhost" in self.base_url or "127.0.0.1" in self.base_url):
            ensure_server_running(background=True)

    def abort(self):
        """Immediately halts ongoing reasoning loop and terminates active subprocesses."""
        self.aborted = True
        try:
            from harness import tools
            tools.terminate_current_process()
        except Exception:
            pass

    @staticmethod
    def classify_query(query: str) -> tuple[str, str]:
        """
        Routes queries based on required cognitive load and provider availability.
        In Auto mode:
        If Gemini cloud is available, routes to fast Gemini Flash Lite (<1s latency, high intelligence).
        If offline, unconfigured, or cloud quota is exhausted, auto-routes to Local Qwen.
        """
        global _CLOUD_EXHAUSTED, _CLOUD_EXHAUSTED_UNTIL
        import time
        if _CLOUD_EXHAUSTED:
            if time.time() < _CLOUD_EXHAUSTED_UNTIL:
                return "local", "Cloud quota currently exhausted; auto-routed to Local Qwen (3b)"
            else:
                _CLOUD_EXHAUSTED = False  # Cooldown passed, re-enable cloud

        q = query.lower()

        # Explicit requests for local or offline execution
        local_keywords = ['offline', 'local model', 'on-device', 'without internet', 'no cloud']
        if any(k in q for k in local_keywords):
            return "local", "Explicit local/offline execution requested"

        if not config.GEMINI_KEY:
            return "local", "No Gemini API key configured; auto-routed to Local Qwen"

        return "gemini", "Gemini Flash Lite (Fast cloud inference)"

    def switch_profile(self, profile_name: str) -> bool:
        """Switch between configured model profiles ('auto', 'gemini', 'local')."""
        if profile_name == "auto":
            self.active_mode = "auto"
            return True
        if profile_name in config.PROFILES:
            self.active_mode = profile_name
            prof = config.PROFILES[profile_name]
            self.model = prof["model"]
            self.base_url = prof["base_url"].rstrip("/")
            self.api_key = prof["api_key"]
            if "11434" in self.base_url and ("localhost" in self.base_url or "127.0.0.1" in self.base_url):
                ensure_server_running(background=True)
            return True
        return False

    @staticmethod
    def _clean_messages_for_model(messages: List[Dict[str, Any]], target_model: str) -> List[Dict[str, Any]]:
        """Cleans messages to ensure universal compatibility across Gemini, Ollama, Groq, and OpenRouter."""
        is_gemini = "gemini" in target_model.lower()
        cleaned = []
        for m in messages:
            m_copy = dict(m)
            if not is_gemini:
                m_copy.pop("extra_content", None)
            if "tool_calls" in m_copy and isinstance(m_copy["tool_calls"], list):
                cleaned_tcs = []
                for tc in m_copy["tool_calls"]:
                    tc_copy = dict(tc)
                    func_info = tc_copy.get("function", {})
                    fn_name = func_info.get("name", "")
                    fn_args = func_info.get("arguments", "{}")
                    if isinstance(fn_args, dict):
                        fn_args = json.dumps(fn_args)
                    cleaned_tc = {
                        "id": str(tc_copy.get("id") or f"call_{fn_name}"),
                        "type": "function",
                        "function": {
                            "name": fn_name,
                            "arguments": fn_args
                        }
                    }
                    if is_gemini and "extra_content" in tc_copy:
                        cleaned_tc["extra_content"] = tc_copy["extra_content"]
                    cleaned_tcs.append(cleaned_tc)
                m_copy["tool_calls"] = cleaned_tcs
            cleaned.append(m_copy)
        return cleaned

    @staticmethod
    def _select_tools(messages: List[Dict[str, Any]], target_model: str) -> List[Dict[str, Any]]:
        """
        Dynamically filters tool schemas to reduce latency and token overhead.
        Sending 37 tool schemas (~15KB) adds massive prefill and token overhead.
        Pruning to relevant tools dramatically accelerates generation and prevents hallucinations.
        """
        all_schemas = registry.get_schemas()

        # Extract text context from user messages and any tools already called
        text_corpus = ""
        used_tool_names = set()
        for m in messages:
            r = m.get("role")
            if r == "user":
                c = m.get("content", "")
                if isinstance(c, str):
                    text_corpus += " " + c.lower()
                elif isinstance(c, list):
                    for part in c:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text_corpus += " " + str(part.get("text", "")).lower()
            elif r == "assistant":
                for tc in m.get("tool_calls", []):
                    fn = tc.get("function", {}).get("name")
                    if fn:
                        used_tool_names.add(fn)
            elif r == "tool":
                fn = m.get("name")
                if fn:
                    used_tool_names.add(fn)

        git_keys = ('git', 'repo', 'repository', 'commit', 'push', 'pull', 'branch', 'diff', 'status', 'remote', 'github', 'gh', 'origin')
        file_keys = ('file', 'read', 'write', 'create', 'delete', 'copy', 'move', 'directory', 'dir', 'folder', 'replace', 'edit', 'path', 'save')
        find_keys = ('find', 'search', 'grep', 'lookup', 'locate', 'where is', 'pattern')
        proc_keys = ('run', 'execute', 'powershell', 'cmd', 'bash', 'terminal', 'python', 'script', 'process', 'task', 'background', 'start', 'stop', 'kill', 'server', 'npm', 'node')
        cloud_keys = ('cloud', 'scraper', 'scrape', 'workflow', 'action', 'actions', 'github action', 'telegram', 'cron', 'schedule', '24/7', 'bot', 'secret')
        web_keys = ('search', 'web', 'google', 'duckduckgo', 'fetch', 'url', 'http', 'https', 'browse')
        calc_keys = ('calc', 'calculate', 'math', 'sqrt', 'expression', 'sum', 'multiply', 'divide', 'equation')
        doc_keys = ('doc', 'document', 'pdf', 'docx', 'xlsx', 'excel', 'csv', 'pptx')
        media_keys = ('image', 'screenshot', 'picture', 'photo', 'vision', 'ocr', 'open')
        mem_keys = ('memory', 'remember', 'recall', 'preference', 'knowledge')
        ws_keys = ('workspace', 'project', 'scaffold', 'switch workspace')

        # Core essential tools are ALWAYS present
        chosen_names = {
            'read_file', 'write_file', 'replace_in_file', 'list_directory',
            'run_powershell'
        }
        chosen_names.update(used_tool_names)

        matched_any_domain = False

        if any(k in text_corpus for k in calc_keys):
            chosen_names.update(['calculate', 'run_python_code'])
            matched_any_domain = True

        if any(k in text_corpus for k in git_keys):
            chosen_names.update([
                'git_status', 'git_diff', 'git_init', 'git_remote_add',
                'git_commit_and_push', 'github_create_repo', 'github_repo_info'
            ])
            matched_any_domain = True

        if any(k in text_corpus for k in file_keys):
            chosen_names.update([
                'read_file_range', 'copy_file', 'move_file', 'delete_file', 'open_file'
            ])
            matched_any_domain = True

        if any(k in text_corpus for k in find_keys):
            chosen_names.update(['find_files', 'search_file_contents'])
            matched_any_domain = True

        if any(k in text_corpus for k in proc_keys):
            chosen_names.update([
                'run_python_code', 'run_background_process',
                'list_background_processes', 'check_background_process', 'stop_background_process'
            ])
            matched_any_domain = True

        if any(k in text_corpus for k in web_keys):
            chosen_names.update(['web_search', 'fetch_webpage', 'download_file'])
            matched_any_domain = True

        if any(k in text_corpus for k in doc_keys):
            chosen_names.update(['read_document', 'download_file'])
            matched_any_domain = True

        if any(k in text_corpus for k in media_keys):
            chosen_names.update(['inspect_image', 'open_file'])
            matched_any_domain = True

        if any(k in text_corpus for k in mem_keys):
            chosen_names.update(['save_memory', 'recall_memory', 'delete_memory', 'save_project_knowledge'])
            matched_any_domain = True

        if any(k in text_corpus for k in ws_keys):
            chosen_names.update(['get_workspace', 'set_workspace', 'create_project', 'save_project_knowledge'])
            matched_any_domain = True

        if any(k in text_corpus for k in cloud_keys):
            chosen_names.update([
                'create_scraper_workflow', 'gh_list_workflows', 'gh_list_runs',
                'gh_trigger_workflow', 'gh_get_run_logs', 'gh_set_secret',
                'test_telegram_bot', 'git_commit_and_push', 'git_status'
            ])
            matched_any_domain = True

        is_local = "localhost" in target_model.lower() or "127.0.0.1" in target_model.lower() or "qwen" in target_model.lower()
        if not is_local and not matched_any_domain:
            return all_schemas

        filtered = [s for s in all_schemas if s.get("function", {}).get("name") in chosen_names]
        return filtered if filtered else all_schemas

    def _call_api(self, messages: List[Dict[str, Any]], with_tools: bool = True) -> Dict[str, Any]:
        """Makes an HTTP POST request with connection pooling, keep-alive, and instant fallback."""
        global _CLOUD_EXHAUSTED, _CLOUD_EXHAUSTED_UNTIL
        import time, re, socket

        max_retries = 3
        pool = _get_http_pool()

        for attempt in range(max_retries):
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "Connection": "keep-alive"
            }
            prepared_messages = self._clean_messages_for_model(messages, self.model)
            payload = {
                "model": self.model,
                "messages": prepared_messages,
                "temperature": self.temperature
            }
            if with_tools:
                payload["tools"] = self._select_tools(messages, self.model)
                payload["tool_choice"] = "auto"

            # 30-second timeout for cloud ensures no false timeouts; 120s for local CPU evaluation
            is_local = "localhost" in self.base_url or "127.0.0.1" in self.base_url
            timeout_sec = 120 if is_local else 30

            encoded_payload = json.dumps(payload).encode("utf-8")

            try:
                if pool and not is_local:
                    import urllib3, io
                    resp = pool.request(
                        "POST",
                        url,
                        body=encoded_payload,
                        headers=headers,
                        timeout=urllib3.Timeout(connect=5.0, read=timeout_sec)
                    )
                    if resp.status == 200:
                        return json.loads(resp.data.decode("utf-8"))
                    else:
                        err_text = resp.data.decode("utf-8", errors="replace")
                        http_err = urllib.error.HTTPError(
                            url, resp.status, err_text, headers, io.BytesIO(resp.data)
                        )
                        http_err.error_body = err_text
                        raise http_err
                else:
                    req = urllib.request.Request(
                        url,
                        data=encoded_payload,
                        headers=headers,
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=timeout_sec) as response:
                        return json.loads(response.read().decode("utf-8"))

            except Exception as e:
                is_timeout = isinstance(e, (TimeoutError, socket.timeout)) or "timed out" in str(e).lower()
                is_http_err = isinstance(e, urllib.error.HTTPError)
                error_body = getattr(e, "error_body", "")
                if not error_body and is_http_err:
                    try:
                        error_body = e.read().decode("utf-8")
                    except Exception:
                        error_body = str(e)
                if not error_body:
                    error_body = str(e)

                is_cloud_fail = (
                    is_timeout or
                    (is_http_err and (
                        e.code in (429, 500, 502, 503, 504) or
                        "high demand" in error_body.lower() or
                        "unavailable" in error_body.lower() or
                        "resource_exhausted" in error_body.lower() or
                        "thought_signature" in error_body.lower()
                    )) or
                    isinstance(e, urllib.error.URLError)
                )

                gemini_fallback = config.PROFILES.get("gemini", {}).get("fallback_model")
                if is_cloud_fail and "gemini" in self.model and gemini_fallback and self.model != gemini_fallback:
                    old_m = self.model
                    self.model = gemini_fallback
                    reason = "Cloud Gemini timed out" if is_timeout else f"Cloud Gemini busy/quota ({getattr(e, 'code', 'error')})"
                    self.pending_events.append({
                        "type": "model_fallback",
                        "from": old_m,
                        "to": self.model,
                        "reason": f"{reason}; switched to cloud fallback ({self.model})"
                    })
                    time.sleep(0.2)
                    continue

                if is_cloud_fail and "gemini" in self.model and "local" in config.PROFILES:
                    _CLOUD_EXHAUSTED = True
                    _CLOUD_EXHAUSTED_UNTIL = time.time() + 60.0
                    local_prof = config.PROFILES["local"]
                    old_m = self.model
                    self.model = local_prof["model"]
                    self.base_url = local_prof["base_url"].rstrip("/")
                    self.api_key = local_prof["api_key"]
                    ensure_server_running(background=True)
                    reason = "Cloud Gemini timed out" if is_timeout else f"Cloud Gemini busy/quota ({getattr(e, 'code', 'error')})"
                    self.pending_events.append({
                        "type": "model_fallback",
                        "from": old_m,
                        "to": self.model,
                        "reason": f"{reason}; seamlessly switched to Local Qwen (3b)"
                    })
                    time.sleep(0.2)
                    continue

                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    continue

                raise RuntimeError(f"Harness Error ({self.model}): {error_body or e}")

    def _call_completion(self, messages: List[Dict[str, Any]], with_tools: bool = True) -> Dict[str, Any]:
        """Invokes _call_api with inspection to ensure compatibility with single-arg mock callables in tests."""
        try:
            import inspect
            sig = inspect.signature(self._call_api)
            if len(sig.parameters) == 1:
                return self._call_api(messages)
            return self._call_api(messages, with_tools=with_tools)
        except Exception:
            return self._call_api(messages)

    def run(self, user_query: str, attachments: Optional[List[Dict[str, Any]]] = None) -> Generator[Dict[str, Any], None, str]:
        """
        Executes the agent loop.
        Supports file and screenshot attachments with native visual reasoning.
        Yields progress trace events: ('thinking', 'tool_call', 'tool_result').
        Returns the final answer string.
        """
        attachments = attachments or []
        has_image = False
        att_lines = []
        for att in attachments:
            p = att.get("path", "")
            is_img = att.get("isImage") or att.get("is_image") or p.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'))
            if is_img:
                has_image = True
                att_lines.append(f"[User Attached Image: '{p}']")
            else:
                att_lines.append(f"[User Attached Document/File: '{p}']")

        effective_query = (user_query or "").strip()
        if att_lines:
            header = "\n".join(att_lines)
            if not effective_query:
                effective_query = "Please review and analyze the attached image(s) / file(s) and provide your findings."
            full_prompt = f"{header}\n\n{effective_query}"
        else:
            full_prompt = effective_query

        if self.active_mode == "auto":
            if has_image:
                target_profile = "gemini"
                reason = "Multimodal visual reasoning (screenshot/image attached)"
            else:
                target_profile, reason = self.classify_query(full_prompt)
            # Switch underlying model for this run without losing history
            prof = config.PROFILES[target_profile]
            self.model = prof["model"]
            self.base_url = prof["base_url"].rstrip("/")
            self.api_key = prof["api_key"]
            if "11434" in self.base_url and ("localhost" in self.base_url or "127.0.0.1" in self.base_url):
                ensure_server_running(background=True)
            yield {
                "type": "routing",
                "target": target_profile,
                "model": self.model,
                "reason": reason
            }

        # Ensure system prompt is always grounded with current live datetime
        current_system_prompt = config.get_system_prompt()
        if not self.history:
            self.history.append({"role": "system", "content": current_system_prompt})
        elif self.history[0]["role"] == "system":
            self.history[0]["content"] = current_system_prompt
        else:
            self.history.insert(0, {"role": "system", "content": current_system_prompt})

        self.aborted = False

        if has_image and "gemini" in self.model:
            content_parts = [{"type": "text", "text": full_prompt}]
            for att in attachments:
                p = att.get("path", "")
                is_img = att.get("isImage") or att.get("is_image") or p.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'))
                if is_img and p and os.path.exists(p):
                    try:
                        import base64, mimetypes
                        mime, _ = mimetypes.guess_type(p)
                        if not mime:
                            ext = os.path.splitext(p)[1].lower()
                            mime = 'image/jpeg' if ext == '.jpg' else f'image/{ext.lstrip(".")}'
                        with open(p, "rb") as f:
                            b64 = base64.b64encode(f.read()).decode("utf-8")
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"}
                        })
                    except Exception:
                        pass
            self.history.append({"role": "user", "content": content_parts})
        else:
            self.history.append({"role": "user", "content": full_prompt})

        PROCESS_MANAGEMENT_TOOLS = {"run_background_process", "list_background_processes", "stop_background_process"}
        NETWORK_TEST_PATTERNS = ["urllib", "socket", "netstat", "localhost", "127.0.0.1", "http.client", "test-netconnection", "curl", "invoke-webrequest"]
        proc_tool_call_count = 0
        bg_process_started = False

        step = 0
        while step < self.max_steps:
            if self.aborted:
                yield {"type": "aborted", "content": "[Generation stopped by user]"}
                return "[Generation stopped by user]"

            step += 1
            yield {"type": "step_start", "step": step}

            try:
                response = self._call_api(self.history)
            except Exception as e:
                if self.aborted:
                    yield {"type": "aborted", "content": "[Generation stopped by user]"}
                    return "[Generation stopped by user]"
                yield {"type": "error", "error": str(e)}
                return f"Harness Error: {e}"

            while self.pending_events:
                yield self.pending_events.pop(0)

            choice = response["choices"][0]
            message = choice.get("message", {})
            self.history.append(message)

            tool_calls = message.get("tool_calls")
            content = message.get("content")

            # Check if model chose to answer directly
            if not tool_calls:
                yield {"type": "final_answer", "content": content or ""}
                return content or "[Empty response]"

            # Process all tool calls requested in this turn
            loop_circuit_broken = False
            for i, tc in enumerate(tool_calls):
                if self.aborted:
                    yield {"type": "aborted", "content": "[Generation stopped by user]"}
                    return "[Generation stopped by user]"
                func_info = tc.get("function", {})
                func_name = func_info.get("name", "")
                raw_args = func_info.get("arguments", "{}")
                tool_call_id = tc.get("id")
                if not tool_call_id:
                    tool_call_id = f"call_{step}_{i}_{func_name}"
                    tc["id"] = tool_call_id

                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    args = {}

                yield {
                    "type": "tool_call",
                    "tool": func_name,
                    "args": args,
                    "id": tool_call_id
                }

                # Execute function in registry
                tool_output = registry.execute(func_name, args)

                # Loop circuit breaker & steering for process management & verification loops
                is_bg_start = (
                    (func_name == "run_background_process" and "started successfully" in tool_output) or
                    ("Background process started successfully" in tool_output)
                )
                if is_bg_start:
                    bg_process_started = True

                is_proc_tool = func_name in PROCESS_MANAGEMENT_TOOLS
                is_verification = False
                if bg_process_started and not is_bg_start:
                    raw_args_str = json.dumps(args).lower() if isinstance(args, dict) else str(args).lower()
                    if is_proc_tool or any(p in raw_args_str for p in NETWORK_TEST_PATTERNS):
                        is_verification = True

                if is_proc_tool or is_verification:
                    proc_tool_call_count += 1

                    if bg_process_started and proc_tool_call_count >= 2:
                        tool_output += (
                            "\n\n[STEERING NOTICE]: The background process is already running. "
                            "Do NOT loop, verify sockets, query netstat, or poll processes. "
                            "You MUST conclude your answer to the user immediately."
                        )
                    elif proc_tool_call_count >= 3:
                        tool_output += (
                            "\n\n[STEERING NOTICE]: Multiple process management calls detected. "
                            "Stop testing or querying processes and conclude your answer now."
                        )

                    if proc_tool_call_count >= 4 or (bg_process_started and proc_tool_call_count >= 3):
                        loop_circuit_broken = True

                yield {
                    "type": "tool_result",
                    "tool": func_name,
                    "args": args,
                    "output": tool_output,
                    "id": tool_call_id
                }

                # Append tool output to message history
                self.history.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": func_name,
                    "content": tool_output
                })

                if loop_circuit_broken:
                    break

            if loop_circuit_broken:
                # Ensure all remaining tool calls in this turn have matching tool responses for OpenAI API spec
                executed_ids = {m.get("tool_call_id") for m in self.history if m.get("role") == "tool"}
                for tc in tool_calls:
                    tc_id = tc.get("id", "call_default")
                    if tc_id not in executed_ids:
                        self.history.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "name": tc.get("function", {}).get("name", "tool"),
                            "content": "[Circuit breaker tripped: Background process is running. Concluding response now.]"
                        })

                conclude_prompt = (
                    "The background task is active and running in the background. "
                    "Conclude your response immediately in 1-2 concise sentences."
                )
                try:
                    final_messages = self.history + [{"role": "user", "content": conclude_prompt}]
                    resp = self._call_completion(final_messages, with_tools=False)
                    answer = resp["choices"][0]["message"].get("content", "")
                    if not answer:
                        answer = "The background process has been started and is actively running."
                except Exception:
                    answer = "The background process has been started and is actively running."

                self.history.append({"role": "assistant", "content": answer})
                yield {"type": "final_answer", "content": answer}
                return answer

        # Circuit breaker reached: request a concise summary of findings so far
        summary_msg = f"[Step Limit Reached]: Max steps ({self.max_steps}) reached."
        try:
            final_req_messages = self.history + [{
                "role": "user",
                "content": f"You reached the maximum step limit ({self.max_steps}). Summarize your findings and progress so far concisely."
            }]
            resp = self._call_completion(final_req_messages, with_tools=False)
            content = resp["choices"][0]["message"].get("content", "")
            if content:
                summary_msg += f"\n\n{content}"
        except Exception:
            pass

        self.history.append({"role": "assistant", "content": summary_msg})
        yield {"type": "circuit_breaker", "content": summary_msg, "max_steps": self.max_steps}
        return summary_msg
