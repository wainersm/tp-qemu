"""
:author: Golita Yue <gyue@redhat.com>
:author: Amos Kong <akong@redhat.com>
"""
import logging
import time
import re
import os

from avocado.core import exceptions

from virttest import data_dir
from virttest import error_context
from virttest import utils_misc
from virttest import utils_test


@error_context.context_aware
def run(test, params, env):
    """
    Run Iometer for Windows on a Windows guest:

    1) Boot guest with additional disk
    2) Format the additional disk
    3) Install and register Iometer
    4) Perpare icf to Iometer.exe
    5) Run Iometer.exe with icf
    6) Copy result to host

    :param test: kvm test object
    :param params: Dictionary with the test parameters
    :param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)

    # diskpart requires windows volume INF file and volume setup
    # events ready, add 10s to wait events done.
    time.sleep(10)
    # format the target disk
    utils_test.run_virt_sub_test(test, params, env, "format_disk")

    error_context.context("Install Iometer", logging.info)
    cmd_timeout = int(params.get("cmd_timeout", 360))
    ins_cmd = params["install_cmd"]
    vol_utils = utils_misc.get_winutils_vol(session)
    if not vol_utils:
        raise exceptions.TestError("WIN_UTILS CDROM not found")
    ins_cmd = re.sub("WIN_UTILS", vol_utils, ins_cmd)
    session.cmd(cmd=ins_cmd, timeout=cmd_timeout)
    time.sleep(0.5)

    error_context.context("Register Iometer", logging.info)
    reg_cmd = params["register_cmd"]
    reg_cmd = re.sub("WIN_UTILS", vol_utils, reg_cmd)
    session.cmd_output(cmd=reg_cmd, timeout=cmd_timeout)

    error_context.context("Prepare icf for Iometer", logging.info)
    icf_name = params["icf_name"]
    ins_path = params["install_path"]
    res_file = params["result_file"]
    icf_file = os.path.join(data_dir.get_deps_dir(), "iometer", icf_name)
    vm.copy_files_to(icf_file, "%s\\%s" % (ins_path, icf_name))

    # Run Iometer
    error_context.context("Start Iometer", logging.info)
    session.cmd("cd %s" % ins_path)
    logging.info("Change dir to: %s" % ins_path)
    run_cmd = params["run_cmd"]
    run_timeout = int(params.get("run_timeout", 1000))
    logging.info("Set Timeout: %ss" % run_timeout)
    run_cmd = run_cmd % (icf_name, res_file)
    logging.info("Execute Command: %s" % run_cmd)
    s, o = session.cmd_status_output(cmd=run_cmd, timeout=run_timeout)
    error_context.context("Copy result '%s' to host" % res_file, logging.info)
    vm.copy_files_from(res_file, test.resultsdir)

    if s != 0:
        raise exceptions.TestFail("iometer test failed. {}".format(o))
