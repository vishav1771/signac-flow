#!/bin/bash
#SBATCH --job-name="SubmissionTe/e5515eac/omp_op/0000/7e483dd1411059a36e848d9980153513"
#SBATCH --partition=compute
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=2

set -e
set -u

cd /Users/vramasub/local/signac-flow/tests/expected_submit_outputs

# omp_op(e5515eac081f886786169793e9b96512)
export OMP_NUM_THREADS=2
/Users/vramasub/miniconda3/envs/main/bin/python /Users/vramasub/local/signac-flow/tests/expected_submit_outputs/project.py exec omp_op e5515eac081f886786169793e9b96512

