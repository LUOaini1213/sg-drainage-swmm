"""Pump and storage screening for an outfall that the tide keeps shut.

With a flap gate (or tidal gate) at the outfall and the sea standing above the
level the drains can tolerate, nothing leaves by gravity: every cubic metre
that reaches the outfall has to be pumped out or held in a sump.  For a pump
of constant capacity Qp the storage needed is the largest accumulated excess
of inflow over Qp; the sump empties at Qp whenever inflow is lower and never
goes below empty (the mass-curve, or sequent-peak, method).

The inflow series is treated as piecewise linear between samples and the
integral is exact for that, including when the inflow crosses Qp inside a
step.  This is a screening estimate: it ignores storage in the drains
themselves, pump start-up and the head the pump works against.
"""
from __future__ import annotations


def storage_required(times_s: list[float], q_in: list[float], qp: float) -> float:
    """Largest sump volume (m3) for pump capacity ``qp`` (m3/s), gate shut
    throughout, sump empty at the start."""
    if len(times_s) != len(q_in) or len(times_s) < 2:
        raise ValueError("need matching time and flow series with at least two samples")
    if qp < 0:
        raise ValueError("pump capacity must not be negative")
    s = smax = 0.0
    for k in range(1, len(times_s)):
        dt = times_s[k] - times_s[k - 1]
        if dt <= 0:
            raise ValueError("times must increase")
        e0, e1 = q_in[k - 1] - qp, q_in[k] - qp
        if e0 >= 0.0 and e1 >= 0.0:            # filling all step long
            s += 0.5 * (e0 + e1) * dt
            smax = max(smax, s)
        elif e0 <= 0.0 and e1 <= 0.0:          # emptying all step long
            s = max(0.0, s + 0.5 * (e0 + e1) * dt)
        else:                                  # inflow crosses Qp inside the step
            tc = dt * e0 / (e0 - e1)
            a1 = 0.5 * e0 * tc
            a2 = 0.5 * e1 * (dt - tc)
            if e0 > 0.0:                       # filling, then emptying: peak at the crossing
                s += a1
                smax = max(smax, s)
                s = max(0.0, s + a2)
            else:                              # emptying, then filling
                s = max(0.0, s + a1) + a2
                smax = max(smax, s)
    return smax


def volume(times_s: list[float], q_in: list[float]) -> float:
    """Total inflow volume (m3), trapezoidal."""
    return sum(0.5 * (q_in[k - 1] + q_in[k]) * (times_s[k] - times_s[k - 1])
               for k in range(1, len(times_s)))


def trade_off(times_s: list[float], q_in: list[float], fractions: list[float]) -> list[dict]:
    """Storage needed for pumps sized at the given fractions of peak inflow."""
    peak = max(q_in)
    return [{"pump_fraction_of_peak": f, "pump_m3s": round(f * peak, 3),
             "storage_m3": round(storage_required(times_s, q_in, f * peak), 1)}
            for f in fractions]
