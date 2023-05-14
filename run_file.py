import docker
import os
import re
import argparse

import os
import subprocess
import sys
from shutil import which

__all__ = ["get_clean_env", "start_command_in_subprocess", "ask_confirmation", "check_program_dependency"]


def get_clean_env():
    env = {}
    env.update(os.environ)

    V = "DOCKER_HOST"
    if V in env:
        msg = "I will ignore %s in the environment because we want to run things on the laptop." % V
        env.pop(V)

    return env


def start_command_in_subprocess(run_cmd, env=None, shell=True, nostdout=False, nostderr=False, retry=1):
    retry = max(retry, 1)
    if env is None:
        env = get_clean_env()
    if shell and not isinstance(run_cmd, str):
        run_cmd = " ".join(run_cmd)
    for trial in range(retry):
        if trial > 0:
            msg = f"An error occurred while running {str(run_cmd)}, retrying (trial={trial + 1})"
        ret = subprocess.run(
            run_cmd,
            shell=shell,
            stdin=sys.stdin,
            stderr=subprocess.PIPE if nostderr else sys.stderr,
            stdout=subprocess.PIPE if nostdout else sys.stdout,
            env=env,
        )
        # exit codes: 0 (ok), 130 (ctrl-c)
        if ret.returncode in [0, 130]:
            break
        else:
            if retry == 1 or retry == trial + 1:
                msg = (
                    f'Error occurred while running "{str(run_cmd)}", '
                    f"please check and retry ({ret.returncode})"
                )
                raise Exception(msg)


def ask_confirmation(message, default="n", question="Do you confirm?", choices=None):
    binary_question = False
    if choices is None:
        choices = {"y": "Yes", "n": "No"}
        binary_question = True
    choices_str = " ({})".format(", ".join([f"{k}={v}" for k, v in choices.items()]))
    default_str = f" [{default}]" if default else ""
    while True:
        r = input(f"{question}{choices_str}{default_str}: ")
        if r.strip() == "":
            r = default
        r = r.strip().lower()
        if binary_question:
            if r in ["y", "yes", "yup", "yep", "si", "aye"]:
                return True
            elif r in ["n", "no", "nope", "nay"]:
                return False
        else:
            if r in choices:
                return r


def check_program_dependency(exe):
    p = which(exe)
    if p is None:
        exit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--branch', type=str, default='daffy')
    parser.add_argument('--bot_name', type=str, default='autobot03')
    parser.add_argument('--container_name', type=str, default='dts-automatic-charging')
    args = parser.parse_args()
    client = docker.from_env()

    arguments = {'image': f'docker.io/duckietown/dt-automatic-charging:{args.branch}-amd64',
                 'name': f'{args.container_name}',
                 'environment': {'VEHICLE_NAME': f'{args.bot_name}',
                                 'ROS_MASTER': f'{args.bot_name}',
                                 'ROS_MASTER_URI': f'http://{args.bot_name}.local:11311',
                                 'HOSTNAME': f'{args.bot_name}',
                                 'QT_X11_NO_MITSHM': 1,
                                 'DISPLAY': ':1'},
                 'stdin_open': True,
                 'tty': True,
                 'detach': True,
                 'privileged': True,
                 'remove': True,
                 'stream': True,
                 'command': 'dt-launcher-default ',
                 'volumes': {'/var/run/avahi-daemon/socket': {'bind': '/var/run/avahi-daemon/socket',
                                                              'mode': 'rw'},
                             '/tmp/.X11-unix': {'bind': '/tmp/.X11-unix',
                                                'mode': 'rw'}},
                 'network_mode': 'host',
                 'ports': {}}

    client.containers.run(**arguments)
    attach_cmd = "docker attach %s" % args.container_name
    try:
        start_command_in_subprocess(attach_cmd)
    except Exception as e:
        pass

