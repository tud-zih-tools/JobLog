## JobLog
This python script queries job information from an HPC job scheduler. The information are stored in a JSON file.
Currently, JobLog supports only SLURM. JobLog queries the following fields of the running job.

This software was developed as part of the EC H2020 funded project NEXTGenIO (Project ID: 671951) http://www.nextgenio.eu.
### Job Information
- JobId
- JobName
- StartTime
- EndTime
- SubmitTime
- NumNodes
- NumCPUs
- NumTasks
- Dependency
- ExitCode

### Job Step Information
- JobID
- NNodes
- NTasks
- NCPUS
- Start
- End
- Elapsed
- JobName
- NodeList
- ExitCode
- State

Job information is once only included in the JSON file and job step information may be contained multiple times.

### Requirements
- Python3
- SLURM and permissions to execute `scontrol` and `sacct`

### Usage
```
> python joblog.py $JOBID /path/to/output
```
The `$JOBID` tells JobLog which job is running and will be used.
The last parameter is used to specify the output directory.
After a successful execution, JobLog created the file `job_log.json` in the output directory.

#### Interactive Jobs
SLURM provides the environment variable `SLURM_EPILOG` to specify an epilog script.
JobLog can be intergrated using an additional epilog script:
```
#!/bin/sh

module load Python

joblog=/path/to/joblog.py

python3 $joblog $SLURM_JOBID $HOME
```
This script can be set before executing the `srun` command.
```
> SLURM_EPILOG="/path/to/epilog_script.sh" srun -n 16 ./app
```

#### Job Script
Just add the execution of JobLog into your job script like that
```
#!/bin/bash
#SBATCH -J HELLOWORLD
#SBATCH --account=zihforschung
#SBATCH --ntasks=4
#SBATCH --time=00:02:00
#SBATCH --partition=haswell

module load OpenMPI Python

srun -n 4 ./mpi_helloworld

python3 /path/to/joblog.py $SLURM_JOBID $HOME
```
You can also use the SLURM epilog variable but than the script will be called multiple times.
Basically, this is not an issue because JobLog will override an existing JSON file.

`example_log.json` contains an example output of a job run with one step.
