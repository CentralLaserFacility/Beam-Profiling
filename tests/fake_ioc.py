"""A fake AWG and scope IOC, for testing the EPICS drivers without hardware.

Serves the PVs that EpicsAwg and EpicsFeedback use. The scope "sees" the first
pulse_points AWG samples, passed through a mild non-linearity, stretched over
the scope slice, on top of a flat background.

Extra PVs for tests:
    FAKE:StuckSample  writes to this AWG sample index are ignored (-1: none)
    FAKE:Reset        write 1 to restore the initial AWG trace and clear faults

Run with: python tests/fake_ioc.py [--options]. Uses EPICS_CAS_* environment variables.
"""

import argparse
import asyncio

import numpy as np
from caproto import ChannelDouble, ChannelInteger
from caproto.server import run

DAC = 4095
BACKGROUND = 0.01
NONLINEARITY = 1.5


def _scalar(value):
    return value[0] if isinstance(value, (list, tuple, np.ndarray)) else value


class FakeHardware:
    def __init__(self, args):
        self.args = args
        self.initial = np.zeros(args.wf_len)
        self.initial[: args.pulse_points + 20] = round(0.4 * DAC)
        self.wf = self.initial.copy()
        self.buffer = np.zeros(args.wf_len)
        self.stuck = -1

    def set_sample(self, i, value):
        if i != self.stuck:
            self.wf[i] = int(np.clip(round(value), 0, DAC))

    def scope_trace(self):
        a = self.args
        trace = np.full(a.scope_len, BACKGROUND)
        pulse = (self.wf[: a.pulse_points] / DAC) ** NONLINEARITY
        x = np.linspace(0, a.pulse_points - 1, a.slice_len)
        trace[a.slice_start : a.slice_start + a.slice_len] += np.interp(
            x, np.arange(a.pulse_points), pulse
        )
        return trace


def make_pvdb(args):
    hw = FakeHardware(args)
    p = args.prefix
    scope = ChannelDouble(value=hw.scope_trace().tolist(), max_length=args.scope_len)
    readback = ChannelInteger(value=hw.wf.astype(int).tolist(), max_length=args.wf_len)
    busy = ChannelInteger(value=0)

    async def refresh_scope():
        await scope.write(hw.scope_trace().tolist())

    class ReadbackProc(ChannelInteger):
        async def write(self, value, **kw):
            await readback.write(hw.wf.astype(int).tolist())
            return await super().write(value, **kw)

    class SetSample(ChannelDouble):
        index = 0

        async def write(self, value, **kw):
            hw.set_sample(self.index, _scalar(value))
            await refresh_scope()
            return await super().write(value, **kw)

    class HoldSample(ChannelDouble):
        index = 0

        async def write(self, value, **kw):
            hw.buffer[self.index] = _scalar(value)
            return await super().write(value, **kw)

    class SetWaveformProc(ChannelInteger):
        async def write(self, value, **kw):
            await busy.write(1)
            for i, v in enumerate(hw.buffer):
                hw.set_sample(i, v * DAC)
            await refresh_scope()
            await asyncio.sleep(0.2)
            await busy.write(0)
            return await super().write(value, **kw)

    class Stuck(ChannelInteger):
        async def write(self, value, **kw):
            hw.stuck = int(_scalar(value))
            return await super().write(value, **kw)

    class Reset(ChannelInteger):
        async def write(self, value, **kw):
            hw.wf = hw.initial.copy()
            hw.stuck = -1
            await readback.write(hw.wf.astype(int).tolist())
            await refresh_scope()
            return await super().write(value, **kw)

    pvdb = {
        p + ":ReadWaveform_ascii_do": readback,
        p + ":ReadWaveform_ascii_do.PROC": ReadbackProc(value=0),
        p + ":DAC": ChannelInteger(value=DAC),
        p + ":_SelScanDisable": ChannelInteger(value=0),
        p + ":SetWaveform.PROC": SetWaveformProc(value=0),
        p + ":SetWaveformBusy": busy,
        args.scope: scope,
        args.scope.split(":")[0] + ":SetResolution": ChannelDouble(value=args.resolution),
        "FAKE:StuckSample": Stuck(value=-1),
        "FAKE:Reset": Reset(value=0),
    }
    for i in range(args.wf_len):
        sample = SetSample(value=0.0)
        sample.index = i
        pvdb["{0}:_SetSample{1}_do".format(p, i)] = sample
        hold = HoldSample(value=0.0)
        hold.index = i
        pvdb["{0}:HoldSampleNorm{1}".format(p, i)] = hold
    return pvdb


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prefix", default="AWG")
    parser.add_argument("--scope", default="SCOPE:CH2:ReadWaveform")
    parser.add_argument("--wf-len", type=int, default=128)
    parser.add_argument("--pulse-points", type=int, default=82)
    parser.add_argument("--scope-len", type=int, default=1000)
    parser.add_argument("--slice-start", type=int, default=273)
    parser.add_argument("--slice-len", type=int, default=410)
    parser.add_argument("--resolution", type=float, default=2.5e-11)
    return parser.parse_args(argv)


if __name__ == "__main__":
    run(make_pvdb(parse_args()), interfaces=["127.0.0.1"], log_pv_names=False)
