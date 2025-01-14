import functools
import itertools
import operator
import subprocess
import os
import shutil
import time
import glob
import errno
import logging

from isp_utils import *

# backend helper to run an ISP simulation with a binary & kernel
# TODO: runFPGA support

logger = logging.getLogger()


# -- MAIN MODULE FUNCTIONALITY

# arguments:
#  exe_path - path to executable to be run
#  kernels_dir - directory containing PEX kernels
#  run_dir - output of this module. Directory to put supporting files, run
#    the simulation, and store the appropriate logs
#  policy - name of the policy to be run
#  sim - name of the simultator to use
#  rule_cache - rule cache configuration tuple. (cache_name, size)
#  gdb - debug port for gdbserver mode (optional)
#  tag_only - run the tagging tools without running the simulator
#  extra - extra command line arguments to the simulator

def runSim(exe_path, policy_dir, run_dir, sim, runtime, rule_cache, gdb, tag_only, soc_cfg, use_validator, extra):
    exe_name = os.path.basename(exe_path)

    if not os.path.isfile(exe_path):
        return retVals.NO_BIN

    if "stock_" not in runtime and use_validator == True:
        if not os.path.isdir(policy_dir):
            if compileMissingPolicy(policy_dir) is False:
                return retVals.NO_POLICY

    doMkDir(run_dir)

    if "stock_" not in runtime and use_validator == True:
        doValidatorCfg(policy_dir, run_dir, exe_name, rule_cache, soc_cfg)
        doEntitiesFile(run_dir, exe_name)

        if tag_only is True:
            return retVals.SUCCESS

    sim_module = __import__("isp_" + sim)
    ret_val = sim_module.runSim(exe_path, run_dir, policy_dir, runtime,
                                gdb, soc_cfg, extra, use_validator)

    return ret_val


def compileMissingPolicy(policy_dir):
    isp_kernel_args = [os.path.basename(policy_dir), "-o",
            os.path.dirname(policy_dir)]

    logger.info("Attempting to compile missing policy")
    subprocess.Popen(["isp_kernel"] + isp_kernel_args).wait()

    if not os.path.isdir(policy_dir):
        logger.error("Failed to compile missing policy")
        return False

    logger.info("Successfully compiled missing policy")
    return True


def doEntitiesFile(run_dir, name):
    filename = os.path.join(run_dir, (name + ".entities.yml"))
    if os.path.exists(filename) is False:
        open(filename, "a").close()


def doValidatorCfg(policy_dir, run_dir, exe_name, rule_cache, soc_cfg):
    rule_cache_name = rule_cache[0]
    rule_cache_size = rule_cache[1]

    logger.info("Using soc_cfg file: {}".format(soc_cfg))

    validatorCfg =  """\
---
   policy_dir: {policyDir}
   tags_file: {tagfile}
   soc_cfg_path: {soc_cfg}
""".format(policyDir=policy_dir,
           tagfile=os.path.join(run_dir, "bininfo", exe_name + ".taginfo"),
           soc_cfg=soc_cfg)

    if rule_cache_name != "":
        validatorCfg += """\
   rule_cache:
      name: {rule_cache_name}
      capacity: {rule_cache_size}
        """.format(rule_cache_name=rule_cache_name, rule_cache_size=rule_cache_size)

    with open(os.path.join(run_dir, "validator_cfg.yml"), 'w') as f:
        f.write(validatorCfg)
