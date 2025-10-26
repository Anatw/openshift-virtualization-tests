import logging
import os

import pexpect
from timeout_sampler import TimeoutSampler

from utilities.constants import (
    TIMEOUT_2MIN,
    TIMEOUT_5MIN,
    VIRTCTL,
)
from utilities.data_collector import get_data_collector_base_directory

LOGGER = logging.getLogger(__name__)


class Console(object):
    def __init__(self, vm, username=None, password=None, timeout=30, prompt=None):
        """
        Connect to VM console

        Args:
            vm (VirtualMachine): VM resource
            username (str): VM username
            password (str): VM password

        Examples:
            from utilities import console
            with console.Console(vm=vm) as vmc:
                vmc.sendline('some command)
                vmc.expect('some output')
        """
        self.vm = vm
        # TODO: `BaseVirtualMachine` does not set cloud-init so the VM is using predefined credentials
        self.username = username or getattr(self.vm, "login_params", {}).get("username") or self.vm.username
        self.password = password or getattr(self.vm, "login_params", {}).get("password") or self.vm.password
        self.timeout = timeout
        self.child = None
        self.login_prompt = "login:"
        self.prompt = prompt if prompt else [r"\$"]
        self.cmd = self._generate_cmd()
        self.base_dir = get_data_collector_base_directory()

    def connect(self):
        LOGGER.info(f"Connect to {self.vm.name} console")
        self.console_eof_sampler(func=pexpect.spawn, command=self.cmd, timeout=self.timeout)

        try:
            self._connect()
        except Exception:
            LOGGER.exception(f"Failed to connect to {self.vm.name} console.")
            self.child.close()
            raise

        return self.child

    def _connect(self):
        self.child.send("\n\n")
        if self.username:
            attempts = 0
            max_attempts = 5
            prompts = self.prompt if isinstance(self.prompt, (list, tuple)) else [self.prompt]
            prompts = list(prompts)  # Ensure it's always a list for concatenation
            while attempts < max_attempts:
                idx = self.child.expect(
                    [self.login_prompt, "Password:"] + prompts + [pexpect.EOF, pexpect.TIMEOUT],
                    timeout=TIMEOUT_2MIN,
                )
                if idx == 0:
                    LOGGER.info(f"{self.vm.name}: Sending username.")
                    self.child.sendline(self.username)
                elif idx == 1:
                    if self.password:
                        LOGGER.info(f"{self.vm.name}: Sending password (masked).")
                        self.child.sendline(self.password)
                    else:
                        raise ValueError("Password prompt received but no password provided.")
                elif 2 <= idx < 2 + len(prompts):
                    LOGGER.info(f"{self.vm.name}: Shell prompt detected.")
                    break
                elif idx == 2 + len(prompts):  # EOF
                    raise pexpect.exceptions.EOF(f"{self.vm.name}: EOF while waiting for login/prompt.")
                else:  # TIMEOUT
                    attempts += 1
                    LOGGER.debug(
                        f"{self.vm.name}: Timeout waiting for login/prompt (attempt {attempts}/{max_attempts})."
                    )
                    self.child.send("\n")
            else:
                raise TimeoutError(f"{self.vm.name}: Unable to reach shell prompt after {max_attempts} attempts.")

    def disconnect(self):
        if self.child.terminated:
            self.console_eof_sampler(func=pexpect.spawn, command=self.cmd, timeout=self.timeout)

        try:
            self.child.send("\n\n")
            self.child.expect(self.prompt)
            if self.username:
                self.child.send("exit")
                self.child.send("\n\n")
                self.child.expect("login:")
        finally:
            self.child.close()

    def console_eof_sampler(self, func, command, timeout):
        sampler = TimeoutSampler(
            wait_timeout=TIMEOUT_5MIN,
            sleep=5,
            func=func,
            exceptions_dict={pexpect.exceptions.EOF: []},
            command=command,
            timeout=timeout,
            encoding="utf-8",
        )
        for sample in sampler:
            if sample:
                self.child = sample
                self.child.logfile = open(f"{self.base_dir}/{self.vm.name}.pexpect.log", "a")
                break

    def _generate_cmd(self):
        virtctl_str = os.environ.get(VIRTCTL.upper(), VIRTCTL)
        cmd = f"{virtctl_str} console {self.vm.name}"
        if self.vm.namespace:
            cmd += f" -n {self.vm.namespace}"
        return cmd

    def __enter__(self):
        """
        Connect to console
        """
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Logout from shell
        """
        self.disconnect()
