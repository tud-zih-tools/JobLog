#!/usr/bin/env python3
from subprocess import Popen, PIPE, check_call
from json import dump as json_dump
import sys, os, argparse
import re
import time
from datetime import datetime, timedelta
#import collections.defaultdict
from collections import defaultdict
from dateutil.tz import tzlocal

JOB_FIELDS = ['JobId', 'JobName', 'StartTime', 'EndTime', 'SubmitTime', 'NumNodes', 'NumCPUs', 'NumTasks', 'Dependency', 'ExitCode']
JOB_STEPS_FIELDS = ['JobID','NNodes','NTasks','NCPUS','Start','End','Elapsed','JobName','NodeList','ExitCode','State', 'Submit']
ACTIVE_STATES = ['COMPLETING', 'PENDING', 'RUNNING', 'CONFIGURING', 'RESIZING']
MAJOR_VERSION = 0
MINOR_VERSION = 1
DATE_INPUT_FORMAT = '%Y-%m-%dT%H:%M:%S'
DATE_OUTPUT_FORMAT = '%Y-%m-%dT%H:%M:%S%z'

def is_integer(num) -> bool:
  try:
    int(num)
    return True
  except:
    return False

def contains_step_id(data: str) -> bool:
  return re.search(r"[0-9]+\.[0-9]+", data) != None

def convert_timestamp(timestamp: str) -> str:
  tmp_date = datetime.strptime(timestamp,DATE_INPUT_FORMAT).astimezone(tzlocal()) 
  return tmp_date.strftime(DATE_OUTPUT_FORMAT)

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

def job_deps(jobid: int) -> str:
  cmd = "scontrol show jobid -dd {}".format(jobid)
  with Popen(cmd, shell=True, stdout=PIPE) as proc:
    for line in proc.stdout:
      l = line.decode("utf-8").rstrip()
      fields = [opts.split('=') for opts in l.split(' ') if opts != '']
      for field in fields:
        if field[0] == 'Dependency':
          return field[1]

def job_info(jobid: int) -> dict:
  job_info = dict()
  job_info["steps"] = dict()
  cmd = "sacct -n -P -j {} --format={}".format(jobid, ','.join(JOB_STEPS_FIELDS))
  with Popen(cmd, shell=True, stdout=PIPE) as proc:
    for line in proc.stdout:
      fields = line.decode("utf-8").rstrip().split('|')
      # Add job info
      if fields[0].isdecimal():
        for k, v in zip(JOB_STEPS_FIELDS, fields):
          if (k == 'Start' or k == 'End' or k == 'Submit'):
            try:
              job_info[k] = convert_timestamp(v)
              print(job_info[k])
            except ValueError:
              job_info[k] = None
          else:
            job_info[k] = v
      # Add job step info
      if contains_step_id(fields[0]):
        job_info["steps"][fields[0]] = dict()
        for k, v in zip(JOB_STEPS_FIELDS[1:], fields[1:]):
          if k == 'Start' or k == 'End':
            v = convert_timestamp(v)
          job_info["steps"][fields[0]][k] = v
  # Create Queue Time
  if 'Start' in job_info and 'Submit' in job_info:
    start_time = datetime.strptime(job_info['Start'], DATE_OUTPUT_FORMAT)
    submit_time = datetime.strptime(job_info['Submit'],DATE_OUTPUT_FORMAT).astimezone(tzlocal())
    #submit_time = datetime.strptime(job_info['SubmitTime'], '%Y-%m-%dT%H:%M:%S')
    job_info['QueueTime'] = str(start_time - submit_time)
  # Add steps if there no one
  if not job_info["steps"]:
    virt_step = {k : job_info[k] for k in JOB_STEPS_FIELDS[1:]}
    if not virt_step['End'] :
      e = datetime.strptime(job_info['Elapsed'] , '%H:%M:%S')
      dt = timedelta(seconds=e.second, minutes=e.minute, hours=e.hour)
      #idx = virt_step['Start'].rfind(':')
      #date_str = virt_step['Start'][:idx] + virt_step['Start'][idx + 1:]
      start = datetime.strptime(virt_step['Start'], DATE_OUTPUT_FORMAT) 
      virt_step['End'] = str(start + dt)
      job_info['End'] = virt_step['End']
    # TODO elif not job_info['End']: update job_info['End'] by counting elapsed times over all steps
    job_info["steps"][job_info['JobID']] = virt_step
    
  return job_info

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("jobid", help="The SLURM job id of the running job.", type=int)
  parser.add_argument("output", help="Path to output directory", type=str)
  args = parser.parse_args()

  wait_on_slurm(args.jobid)

  if not os.path.exists(args.output):
    sys.exit("Given path does not exist.")

  info = job_info(args.jobid)
  info.update({  "Version" : {"Major" : MAJOR_VERSION, "Minor" : MINOR_VERSION }})
  if not job_active(args.jobid):
    print("[INFO] Could not determine job dependencies because your job is not alive.")
  else:
    info.update({'Dependency': job_deps(args.jobid)})

  export_json(args.output, info)

