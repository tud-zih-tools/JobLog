#!/usr/bin/env python3
from subprocess import Popen, PIPE, check_call
from json import dump as json_dump
import sys, os, argparse
from datetime import datetime, timedelta

JOB_FIELDS = ['JobId', 'JobName', 'StartTime', 'EndTime', 'SubmitTime', 'NumNodes', 'NumCPUs', 'NumTasks', 'Dependency', 'ExitCode']
JOB_STEPS_FIELDS = ['JobID','NNodes','NTasks','NCPUS','Start','End','Elapsed','JobName','NodeList','ExitCode','State']

def is_integer(num) -> bool:
  try:
    int(num)
    return True
  except:
    return False

def get_job_desc(jobid: int) -> None:
  job_desc = dict()
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

def get_job_steps(jobid: int) -> dict:
  job_steps = dict()
  cmd = "sacct -n -P -j {} --format={}".format(jobid, ','.join(JOB_STEPS_FIELDS))
  with Popen(cmd, shell=True, stdout=PIPE) as proc:
    for line in proc.stdout:
      fields = line.decode("utf-8").rstrip().split('|')
      if not is_integer(fields[0]) or int(fields[0]) != jobid:
        job_steps[fields[0]] = {k: v for k, v in zip(JOB_STEPS_FIELDS[1:], fields[1:])}
  return job_steps

def job_exists(jobid: int):
  cmd = "scontrol show jobid {}".format(jobid)
  with Popen(cmd, shell=True,stdout=PIPE) as proc:
    proc.wait()
    return proc.returncode == 0

def export_json(path: str, job_desc: dict) -> None:
  with open("{}/job_log.json".format(path),'w') as file:
    json_dump(job_desc, file)

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("jobid", help="The SLURM job id of the running job.", type=int)
  parser.add_argument("output", help="Path to output directory", type=str)
  args = parser.parse_args()

  if not os.path.exists(args.output):
    sys.exit("Given path does not exist.")

  if not job_exists(args.jobid):
    sys.exit("Given job does not exist.")

  job_desc = get_job_desc(args.jobid)
  job_desc['steps'] = get_job_steps(args.jobid)
  export_json(args.output, job_desc)
