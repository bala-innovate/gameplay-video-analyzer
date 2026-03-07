# Functions that may come in handy later on
import numpy as np

def _assign_role_bands(id_to_side, id_to_initial_y):
    """
    Approximate position-groups (e.g., line/back/deep) per side by vertical bands
    from the first reliable labeled frame. Returns track_id -> band index.
    """
    side_to_ids = {"A": [], "D": []}
    for tid, side in id_to_side.items():
        if tid in id_to_initial_y:
            side_to_ids.setdefault(side, []).append(tid)

    id_to_band = {}
    for side, ids in side_to_ids.items():
        if not ids:
            continue
        ys = np.array([id_to_initial_y[i] for i in ids], dtype=float)
        q1 = float(np.quantile(ys, 0.33))
        q2 = float(np.quantile(ys, 0.66))
        for tid in ids:
            y = float(id_to_initial_y[tid])
            if y <= q1:
                id_to_band[tid] = 0
            elif y <= q2:
                id_to_band[tid] = 1
            else:
                id_to_band[tid] = 2
    return id_to_band