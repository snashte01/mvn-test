from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional
import paramiko

logger = logging.getLogger(__name__)


class SSHResult:
    def __init__(self, stdout: str, stderr: str, exit_code: int):
        self.stdout = stdout.strip()
        self.stderr = stderr.strip()
        self.exit_code = exit_code

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def __repr__(self):
        return f"SSHResult(exit_code={self.exit_code}, stdout={self.stdout!r})"


class SSHClient:
    def __init__(self, host: str, user: str, key_file: str, port: int = 22):
        self.host = host
        self.user = user
        self.key_file = str(Path(key_file).expanduser())
        self.port = port
        self._client: Optional[paramiko.SSHClient] = None

    def connect(self):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=self.host,
            port=self.port,
            username=self.user,
            key_filename=self.key_file,
            timeout=30,
        )
        self._client = client
        logger.debug("Connected to %s@%s:%d", self.user, self.host, self.port)

    def disconnect(self):
        if self._client:
            self._client.close()
            self._client = None

    def run(self, command: str, timeout: int = 120) -> SSHResult:
        if self._client is None:
            self.connect()
        logger.debug("[%s] $ %s", self.host, command)
        stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        result = SSHResult(out, err, exit_code)
        logger.debug("[%s] exit=%d", self.host, exit_code)
        return result

    def sudo(self, command: str, timeout: int = 120) -> SSHResult:
        return self.run(f"sudo {command}", timeout=timeout)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.disconnect()
