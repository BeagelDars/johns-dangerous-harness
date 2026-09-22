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
        Routes queries based on required cognitive load.
        Simple text review, scraping, extraction, file listing, git operations -> Local (saves API quota).
        Complex logic, coding, debugging, architectural design -> Cloud Gemini.
        """
        global _CLOUD_EXHAUSTED
        if _CLOUD_EXHAUSTED:
            return "local", "Cloud quota currently exhausted; auto-routed to Local Qwen (3b)"

        q = query.lower()

        complex_keywords = [
            'debug', 'fix bug', 'architect', 'refactor', 'design', 'algorithm',
            'why does', 'deep research', 'plan a', 'solve complex', 'write code',
            'build an app', 'optimize', 'implement', 'research', 'search the web',
            'google', 'duckduckgo', 'look up', 'latest', 'news about'
        ]
        routine_keywords = [
            'scrape', 'scraping', 'fetch', 'extract', 'review text', 'summarize',
            'read file', 'list files', 'list dir', 'calculate', 'count lines',
            'format text', 'clean up', 'parse text', 'regex',
            'git', 'status', 'push', 'commit', 'branch', 'diff', 'init', 'github', 'repo'
        ]

        has_complex = any(k in q for k in complex_keywords)
        has_routine = any(k in q for k in routine_keywords)

        if has_routine and not has_complex:
            return "local", "Routine task (git / text processing / basic lookup)"
        return "gemini", "High-cognition / Research / Multi-step task"

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
        cleaned = []
        for m in messages:
            m_copy = dict(m)
            m_copy.pop("extra_content", None)
            if "tool_calls" in m_copy and isinstance(m_copy["tool_calls"], list):
                cleaned_tcs = []
                for tc in m_copy["tool_calls"]:
                    tc_copy = dict(tc)
                    tc_copy.pop("extra_content", None)
                    func_info = tc_copy.get("function", {})
                    fn_name = func_info.get("name", "")
                    fn_args = func_info.get("arguments", "{}")
                    if isinstance(fn_args, dict):
                        fn_args = json.dumps(fn_args)
                    cleaned_tcs.append({
                        "id": str(tc_copy.get("id") or f"call_{fn_name}"),
                        "type": "function",
                        "function": {
                            "name": fn_name,
                            "arguments": fn_args
                        }
                    })
                m_copy["tool_calls"] = cleaned_tcs
            cleaned.append(m_copy)
        return cleaned

    @staticmethod
    def _select_tools(messages: List[Dict[str, Any]], target_model: str) -> List[Dict[str, Any]]:
        """
        Dynamically filters tool schemas to reduce CPU latency on local models.
        Sending 35 tool schemas on CPU Ollama takes ~75s; sending 6-10 focused tools takes ~7-10s.
        """
        all_schemas = registry.get_schemas()
        is_local = "localhost" in target_model.lower() or "127.0.0.1" in target_model.lower() or "qwen" in target_model.lower()
        if not is_local:
            return all_schemas

        # Extract text context ONLY from user messages (ignore system prompt rules)
        text_corpus = ""
        for m in messages:
            if m.get("role") == "user":
                c = m.get("content", "")
                if isinstance(c, str):
                    text_corpus += " " + c.lower()

        git_keys = ('git', 'repo', 'repository', 'commit', 'push', 'pull', 'branch', 'diff', 'status', 'remote', 'github', 'gh', 'origin')
        file_keys = ('file', 'read', 'write', 'create', 'delete', 'copy', 'move', 'directory', 'dir', 'folder', 'replace', 'edit', 'path', 'save')
        proc_keys = ('run', 'execute', 'powershell', 'cmd', 'bash', 'terminal', 'python', 'script', 'process', 'task', 'background', 'start', 'stop', 'kill', 'server', 'npm', 'node')
        web_keys = ('search', 'web', 'google', 'duckduckgo', 'fetch', 'url', 'http', 'https', 'scrape', 'browse')

        # Core essential tools are ALWAYS present
        chosen_names = {
            'read_file', 'write_file', 'replace_in_file', 'list_directory',
            'run_powershell'
        }

        # Independent checks so multi-domain requests (e.g. create app + git) get all needed tools
        if any(k in text_corpus for k in git_keys):
            chosen_names.update([
                'git_status', 'git_diff', 'git_init', 'git_remote_add',
                'git_commit_and_push', 'github_create_repo', 'github_repo_info'
            ])

        if any(k in text_corpus for k in file_keys):
            chosen_names.update([
                'copy_file', 'move_file', 'delete_file'
            ])

        if any(k in text_corpus for k in proc_keys):
            chosen_names.update([
                'run_python_code', 'run_background_process',
                'get_background_tasks', 'stop_background_process'
            ])

        if any(k in text_corpus for k in web_keys):
            chosen_names.update([
                'fetch_web_content', 'duckduckgo_search'
            ])

        filtered = [s for s in all_schemas if s.get("function", {}).get("name") in chosen_names]
        return filtered if filtered else all_schemas

    def _call_api(self, messages: List[Dict[str, Any]], with_tools: bool = True) -> Dict[str, Any]:
        """Makes an HTTP POST request with automated instant fallback to local Qwen on cloud slowdown/error."""
        global _CLOUD_EXHAUSTED
        import time, re, socket

        max_retries = 3
        for attempt in range(max_retries):
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
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

            # Tight 5-second timeout for cloud so user never hangs; 120s for local CPU evaluation
            is_local = "localhost" in self.base_url or "127.0.0.1" in self.base_url
            timeout_sec = 120 if is_local else 5

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )

            try:
                with urllib.request.urlopen(req, timeout=timeout_sec) as response:
                    return json.loads(response.read().decode("utf-8"))

            except Exception as e:
                is_timeout = isinstance(e, (TimeoutError, socket.timeout)) or "timed out" in str(e).lower()
                is_http_err = isinstance(e, urllib.error.HTTPError)
                error_body = ""
                if is_http_err:
                    try:
                        error_body = e.read().decode("utf-8")
                    except Exception:
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

                if is_cloud_fail and "gemini" in self.model and "local" in config.PROFILES:
                    _CLOUD_EXHAUSTED = True
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
