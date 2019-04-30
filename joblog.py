#!/usr/bin/env python3
from subprocess import Popen, PIPE, check_call
from json import dump as json_dump
import sys, os, argparse
import re
import time
from datetime import datetime, timedelta
from dateutil.tz import tzlocal

JOB_FIELDS = ['JobId', 'JobName', 'StartTime', 'EndTime', 'SubmitTime', 'NumNodes', 'NumCPUs', 'NumTasks', 'Dependency', 'ExitCode']
JOB_STEPS_FIELDS = ['JobID','NNodes','NTasks','NCPUS','Start','End','Elapsed','JobName','NodeList','ExitCode','State']
ACTIVE_STATES = ['COMPLETING', 'PENDING', 'RUNNING', 'CONFIGURING', 'RESIZING']
MAJOR_VERSION = 0
MINOR_VERSION = 1

def is_integer(num) -> bool:
  try:
    int(num)
    return True
  except:
    return False

def get_job_desc(jobid: int, job_desc: dict) -> None:
  cmd = "scontrol show jobid -dd {}".format(jobid)
  with Popen(cmd, shell=True, stdout=PIPE) as proc:
    for line in proc.stdout:
      l = line.decode("utf-8").rstrip()
      fields = [opts.split('=') for opts in l.split(' ') if opts != '']
      for field in fields:
        if field[0] in JOB_FIELDS:
          job_desc[field[0]] = field[1]
  if 'StartTime' in job_desc and 'SubmitTime' in job_desc:
    start_time = datetime.strptime(job_desc['StartTime'], '%Y-%m-%dT%H:%M:%S')
    submit_time = datetime.strptime(job_desc['SubmitTime'], '%Y-%m-%dT%H:%M:%S')
    job_desc['QueueTime'] = str(start_time - submit_time)
  return job_desc

def contains_step_id(data: str) -> bool:
  return re.search(r"[0-9]+\.[0-9]+", data) != None

def convert_timestamp(timestamp: str) -> datetime:
  return datetime.strptime(timestamp,'%Y-%m-%dT%H:%M:%S').astimezone(tzlocal())

def get_job_steps(jobid: int) -> dict:
  job_steps = dict()
  cmd = "sacct -n -P -j {} --format={}".format(jobid, ','.join(JOB_STEPS_FIELDS))
  with Popen(cmd, shell=True, stdout=PIPE) as proc:
    for line in proc.stdout:
      fields = line.decode("utf-8").rstrip().split('|')
      if contains_step_id(fields[0]):
        job_steps[fields[0]] = dict()
        for k, v in zip(JOB_STEPS_FIELDS[1:], fields[1:]):
          if k == 'Start' or k == 'End':
            job_steps[fields[0]][k] = str(convert_timestamp(v))
          else:
            job_steps[fields[0]][k] = v
  return job_steps

def job_exists(jobid: int):
  cmd = "scontrol show jobid {}".format(jobid)
  with Popen(cmd, shell=True,stdout=PIPE) as proc:
    proc.wait()
    return proc.returncode == 0

def export_json(path: str, job_desc: dict) -> None:
  with open("{}/job_log.json".format(path),'w') as file:
    json_dump(job_desc, file)

def job_has_steps(jobid: int) -> bool:
  cmd  = "sacct -j {} --format=JobID --nohead".format(jobid)
  regex = r"[0-9]+\.[0-9]+"
  with Popen(cmd, shell=True, stdout=PIPE) as proc:
    proc.wait()
    data = proc.stdout.read().decode("utf-8")
    return re.search(regex, data) != None

def steps_active(jobid: int) -> bool:
  cmd = "sacct -j {} --format=JobID,State --nohead".format(jobid)
  with Popen(cmd, shell=True, stdout=PIPE) as proc:
    proc.wait()
    all_steps = [step.decode("utf-8").rstrip() for step in proc.stdout if contains_step_id(step.decode("utf-8"))]
    return any(map(lambda s: s.split()[1] in ACTIVE_STATES, all_steps))

def job_active(jobid: int) -> bool:
  cmd = "sacct -j {} --format=State --nohead".format(jobid)
  with Popen(cmd, shell=True, stdout=PIPE) as proc:
    proc.wait()
    state = proc.stdout.read().decode("utf-8").rstrip()
    return state in ACTIVE_STATES

def wait_on_slurm(jobid: int) -> None:
  wait_time = 0.1
  if job_has_steps(jobid):
    while steps_active(jobid):
      time.sleep(wait_time)
  else:
    while job_active(jobid):
      time.sleep(wait_time)

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("jobid", help="The SLURM job id of the running job.", type=int)
  parser.add_argument("output", help="Path to output directory", type=str)
  args = parser.parse_args()

  wait_on_slurm(args.jobid)

  if not os.path.exists(args.output):
    sys.exit("Given path does not exist.")

  if not job_exists(args.jobid):
    sys.exit("Given job does not exist.")

  job_desc = {  "Version" : {"Major" : MAJOR_VERSION, "Minor" : MINOR_VERSION }}
  get_job_desc(args.jobid, job_desc)
  job_desc['steps'] = get_job_steps(args.jobid)
  export_json(args.output, job_desc)
