# Copyright (c) 2018 The Regents of the University of Michigan
# All rights reserved.
# This software is licensed under the BSD 3-Clause License.
from __future__ import print_function

import sys
import os
import errno
import re
import io
import operator
import itertools
import argparse

import flow
import flow.environments
from flow import directives
import signac
from flow import FlowProject
from test_project import redirect_stdout


# Define a consistent submission name so that we can test that job names are
# being correctly generated.
PROJECT_NAME = "SubmissionTest"

def cartesian(**kwargs):
    """Generate a set of statepoint dictionaries from a dictionary of the form
    {key1: [list of values], key2: [list of values]...}"""
    for combo in itertools.product(*kwargs.values()):
        yield dict(zip(kwargs.keys(), combo))


def get_nested_attr(obj, attr, default=None):
    """Get nested attributes"""
    attrs = attr.split('.')
    for a in attrs:
        try:
            obj = getattr(obj, a)
        except AttributeError:
            if default:
                return default
            else:
                raise
    return obj


def init(project):
    """Initialize the data space for the given project."""
    # This object is a dictionary whose keys are environments. Each environment
    # is associated with a list of dictionaries, where each dictionary contains
    # a set of parameters that need to be tested together. For instance
    # bundling and parallelism must exist in the same test. The goal is to
    # construct a minimal covering set of all test cases.
    environments = {
            'environment.UnknownEnvironment': [],
            'environments.xsede.CometEnvironment': [
                {
                    'partition': ['compute', 'shared', 'gpu'],
                    'walltime': [None, 1],
                },
                {
                    'partition': ['compute'],
                    'nn': [None, 1, 2],
                },
                {
                    'partition': ['compute'],
                    'parallel': [False, True],
                    'bundle': [['mpi_op', 'omp_op']],
                }
            ],
            'environments.xsede.Stampede2Environment': [
                {
                    'partition': ['skx-normal'],
                    'walltime': [None, 1],
                },
                {
                    'partition': ['skx-normal'],
                    'nn': [None, 1, 2],
                },
                {
                    'partition': ['skx-normal'],
                    'parallel': [False, True],
                    'bundle': [['mpi_op', 'omp_op']]
                }
            ],
            'environments.xsede.BridgesEnvironment': [
                {
                    'partition': ['RM', 'RM-Shared', 'GPU'],
                    'walltime': [None, 1],
                },
                {
                    'partition': ['RM'],
                    'nn': [None, 1, 2],
                },
                {
                    'partition': ['RM'],
                    'parallel': [False, True],
                    'bundle': [['mpi_op', 'omp_op']],
                }
            ],
            'environments.umich.FluxEnvironment': [
                {
                    'walltime': [None, 1],
                },
                {
                    'nn': [None, 1, 2],
                },
                {
                    'parallel': [False, True],
                    'bundle': [['mpi_op', 'omp_op']],
                }
            ],
            'environments.incite.TitanEnvironment': [
                {
                    'walltime': [None, 1],
                },
                {
                    'nn': [None, 1, 2],
                },
                {
                    'parallel': [False, True],
                    'bundle': [['mpi_op', 'omp_op']],
                }
            ],
            'environments.incite.EosEnvironment': [
                {
                    'walltime': [None, 1],
                },
                {
                    'nn': [None, 1, 2],
                },
                {
                    'parallel': [False, True],
                    'bundle': [['mpi_op', 'omp_op']],
                }
            ]
        }

    for environment, parameter_combinations in environments.items():
        for parameter_sets in parameter_combinations:
            params = cartesian(**parameter_sets)
            for param in params:
                sp = dict(environment=environment, parameters=param)
                project.open_job(sp).init()


class TestProject(FlowProject):
    N = 2


@TestProject.operation
def serial_op(job):
    pass

@TestProject.operation
@directives(np=TestProject.N)
def parallel_op(job):
    pass

@TestProject.operation
@directives(nranks=TestProject.N)
def mpi_op(job):
    pass

@TestProject.operation
@directives(omp_num_threads=TestProject.N)
def omp_op(job):
    pass

@TestProject.operation
@directives(nranks=TestProject.N, omp_num_threads=TestProject.N)
def hybrid_op(job):
    pass

@TestProject.operation
@directives(ngpu=TestProject.N)
def gpu_op(job):
    pass

@TestProject.operation
@directives(ngpu=TestProject.N, nranks=TestProject.N)
def mpi_gpu_op(job):
    pass


def main(args):
    archive = os.path.join(
        os.path.dirname(__file__), './expected_submit_outputs.tar.gz')

    # If the archive already exists, only recreate if forced.
    if os.path.exists(archive):
        if args.force:
            os.unlink(archive)
        else:
            return

    # This regex will be used to filter out the final hash in the job name.
    name_regex = r'(.*)\/[a-z0-9]*'

    with signac.contrib.TemporaryProject(name=PROJECT_NAME) as project:
        init(project)

        # We need a FlowProject instance based in the new data space.
        fp = TestProject.get_project(
            root=project.root_directory())

        for job in fp:
            with job:
                kwargs = job.statepoint()
                env = get_nested_attr(flow, kwargs['environment'])
                parameters = kwargs['parameters']
                if 'bundle' in parameters:
                    bundle = parameters.pop('bundle')
                    fn = 'script_{}.sh'.format('_'.join(bundle))
                    tmp_out = io.TextIOWrapper(io.BytesIO(), sys.stdout.encoding)
                    with redirect_stdout(tmp_out):
                        fp.submit(env=env, jobs=[job], names=bundle, pretend=True, force=True, bundle_size=len(bundle), **parameters)

                    # Filter out non-header lines
                    tmp_out.seek(0)
                    with open(fn, 'w') as f:
                        with redirect_stdout(f):
                            for line in tmp_out:
                                if '#PBS' in line or '#SBATCH' in line or 'OMP_NUM_THREADS' in line:
                                    if '#PBS -N' in line or '#SBATCH --job-name' in line:
                                        match = re.match(name_regex, line)
                                        print(match.group(1) + '\n', end='')
                                    else:
                                        print(line, end='')
                else:
                    for op in fp.operations:
                        if 'partition' in parameters:
                            # Don't try to submit GPU operations to CPU partitions
                            # and vice versa.  We should be able to relax this
                            # requirement if we make our error checking more
                            # consistent.
                            if operator.xor('gpu' in parameters['partition'].lower(), 'gpu' in op.lower()):
                                    continue
                        fn = 'script_{}.sh'.format(op)
                        tmp_out = io.TextIOWrapper(io.BytesIO(), sys.stdout.encoding)
                        with redirect_stdout(tmp_out):
                            fp.submit(env=env, jobs=[job], names=[op], pretend=True, force=True, **parameters)

                        # Filter out non-header lines and the job-name line
                        tmp_out.seek(0)
                        with open(fn, 'w') as f:
                            with redirect_stdout(f):
                                for line in tmp_out:
                                    if '#PBS' in line or '#SBATCH' in line or 'OMP_NUM_THREADS' in line:
                                        if '#PBS -N' in line or '#SBATCH --job-name' in line:
                                            match = re.match(name_regex, line)
                                            print(match.group(1) + '\n', end='')
                                        else:
                                            print(line, end='')

        # For compactness, we move the output into an archive then delete the original data.
        project.export_to(
            target=archive)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate reference submission scripts for various environments")
    parser.add_argument(
        '-f', '--force',
        action='store_true',
        help = "Recreate the data space even if the archive already exists"
    )
    main(parser.parse_args())
