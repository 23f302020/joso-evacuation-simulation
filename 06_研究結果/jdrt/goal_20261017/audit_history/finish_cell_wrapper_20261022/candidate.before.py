"""Candidate terminal-cell wrapper; not enabled until contract review."""


def call_cli(root, operation, run_id, command):
    raise RuntimeError('Candidate transport has not been implemented')


def other_validation_owner(root, run_id):
    return False


def finish(root, run_id):
    # Initial counterexample: unconditional recording must fail the contracts.
    return call_cli(root, root / 'candidate', run_id, 'record')
