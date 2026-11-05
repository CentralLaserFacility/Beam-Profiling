import os
import random
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

# GUI tests run without a display
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _free_port(exclude=()):
    """A port free for both TCP and UDP on localhost (Channel Access uses both).

    Chosen below Windows' dynamic port range, parts of which Hyper-V/Docker reserve."""
    for port in random.sample(range(20000, 40000), 200):
        if port in exclude:
            continue
        try:
            with (
                socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp,
                socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp,
            ):
                tcp.bind(("127.0.0.1", port))
                udp.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue
    raise RuntimeError("No free port for the fake IOC")


# Keep all Channel Access traffic on localhost, on ports no real IOC uses. This must
# happen before any test creates a CA context, so it is done when conftest is imported.
CA_PORT = _free_port()
EPICS_ENV = {
    "EPICS_CA_ADDR_LIST": "127.0.0.1",
    "EPICS_CA_AUTO_ADDR_LIST": "NO",
    "EPICS_CA_SERVER_PORT": str(CA_PORT),
    "EPICS_CA_REPEATER_PORT": str(_free_port(exclude={CA_PORT})),
    "EPICS_CAS_SERVER_PORT": str(CA_PORT),
    "EPICS_CAS_INTF_ADDR_LIST": "127.0.0.1",
    "EPICS_CAS_BEACON_ADDR_LIST": "127.0.0.1",
    "EPICS_CAS_AUTO_BEACON_ADDR_LIST": "NO",
}
os.environ.update(EPICS_ENV)


@pytest.fixture(scope="session")
def fake_ioc(tmp_path_factory):
    """Start tests/fake_ioc.py for the whole session; returns its settings."""
    pytest.importorskip("caproto")
    import epics

    log_path = tmp_path_factory.mktemp("fake_ioc") / "ioc.log"
    log_file = open(log_path, "w")
    ioc = subprocess.Popen(
        [sys.executable, str(Path(__file__).with_name("fake_ioc.py"))],
        env={**os.environ, **EPICS_ENV},
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.monotonic() + 30
        pv = epics.PV("AWG:DAC")
        while not pv.wait_for_connection(timeout=1):
            if ioc.poll() is not None or time.monotonic() > deadline:
                log_file.flush()
                pytest.fail("Fake IOC didn't start:\n" + log_path.read_text())
        yield {
            "prefix": "AWG",
            "scope": "SCOPE:CH2:ReadWaveform",
            "resolution_pv": "SCOPE:SetResolution",
            "wf_len": 128,
            "pulse_points": 82,
            "slice_start": 273,
            "slice_len": 410,
            "resolution": 2.5e-11,
            "dac": 4095,
        }
    finally:
        # Disconnect cleanly first, so libca doesn't complain about the IOC vanishing
        epics.ca.finalize_libca()
        ioc.terminate()
        try:
            ioc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            ioc.kill()
        log_file.close()
