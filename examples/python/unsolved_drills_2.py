"""Original unsolved SDE II practice, edition II. No reference solutions.

Fill the functions, then run: python examples/python/drill_grader_2.py
These exercises are independently curated, not recovered assessment questions.
"""
def minimum_batch_capacity(loads, max_batches):
    """Minimum possible largest sum among at most max_batches nonempty,
    contiguous batches preserving order; loads are nonnegative integers.

    Empty loads return 0. max_batches >= 1.
    """
    raise NotImplementedError("implement minimum_batch_capacity")

def islands_after_activation(rows, columns, additions):
    """For each (r,c) in additions, activate that grid cell permanently and
    return the number of 4-neighbor connected active components afterward.

    Initially all inactive. Duplicate activations do nothing.
    0 <= r < rows, 0 <= c < columns for each action.
    """
    raise NotImplementedError("implement islands_after_activation")
