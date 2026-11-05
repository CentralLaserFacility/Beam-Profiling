"""Wires the core loop to real or simulated hardware. No GUI code here."""

import logging

from beam_shaper.core.diagnostics import DiagnosticWriter
from beam_shaper.core.loop import LoopEngine, LoopParameters
from beam_shaper.core.plugins import load_awg_filter, load_correction_algorithm
from beam_shaper.core.settings import num_points

log = logging.getLogger(__name__)


def build_engine(
    config,
    settings,
    target,
    background,
    scope_pv=None,
    time_resolution_pv=None,
    sim_write_time=3.0,
):
    """
    Create a LoopEngine for one run.

    target, background: TargetCurve and BkgCurve
    scope_pv, time_resolution_pv: epics.PV objects, only needed when not simulating
    Returns (engine, warnings) where warnings is a list of (message, caption) for the user.
    """
    warnings = []
    correction_fn, err = load_correction_algorithm(config.path("algorithm"))
    if err:
        warnings.append((err, "Correction algorithm error"))
    filter_fn, err = load_awg_filter(config.path("filter"))
    if err:
        warnings.append((err, "Filter error"))

    n = num_points(settings.pulse_length, config.awg_ns_per_point)
    crop = (settings.slice_start, settings.slice_length)
    if config.sim:
        from beam_shaper.hardware.sim import SimAwg, SimFeedback, simulated_start_shape

        awg = SimAwg(simulated_start_shape(background, crop, n), write_time=sim_write_time)
        feedback = SimFeedback(awg)
    else:
        from beam_shaper.hardware.epics_awg import EpicsAwg
        from beam_shaper.hardware.epics_scope import EpicsFeedback

        awg = EpicsAwg(
            config.awg_prefix,
            n,
            settings.max_percent_change,
            config.awg_write_method,
            config.awg_wait,
        )
        feedback = EpicsFeedback(
            scope_pv,
            time_resolution_pv,
            background,
            crop,
            n,
            settings.averages,
            config.scope_wait,
        )

    log.info(
        "New run (%s): %s; target %s; algorithm %s; filter %s",
        "simulation" if config.sim else "hardware",
        settings,
        target.name(),
        config.path("algorithm"),
        config.path("filter"),
    )
    diagnostics = None
    if settings.save_diag_files:
        run_info = {"settings": settings, "config": config, "target": target.name()}
        diagnostics = DiagnosticWriter(config.path("diag"), run_info)

    engine = LoopEngine(
        target.get_processed(),
        LoopParameters.from_settings(config, settings),
        awg,
        feedback,
        correction_fn=correction_fn,
        filter_fn=filter_fn,
        diagnostics=diagnostics,
        background_raw=background.get_raw(),
    )
    return engine, warnings


def prepare_worker_thread(sim):
    """Call at the start of any thread that will talk to hardware."""
    if not sim:
        from beam_shaper.hardware.epics_scope import attach_to_thread

        attach_to_thread()


def check_installation(config, out=print):
    """Check config, curve library, user files and EPICS libraries without starting the GUI.

    Reports each check through out(). Returns True if everything is usable."""
    import numpy as np

    from beam_shaper.core.curve import library_curves

    ok = True

    def report(passed, message):
        nonlocal ok
        ok = ok and passed
        out("{0}  {1}".format("OK  " if passed else "FAIL", message))

    report(True, "Mode: {0}".format("simulation" if config.sim else "hardware"))
    curves = library_curves(config.path("curve"))
    report(bool(curves), "{0} target shape(s) in {1}".format(len(curves), config.path("curve")))

    algorithm, err = load_correction_algorithm(config.path("algorithm"))
    report(err is None, err or "Correction algorithm: " + config.path("algorithm"))
    filter_fn, err = load_awg_filter(config.path("filter"))
    if err is None:
        try:
            filter_fn(np.linspace(0, 1, 82))
        except Exception as e:
            err = "Filter failed on a test trace: {0}".format(e)
    report(err is None, err or "AWG filter: " + config.path("filter"))

    try:
        config.ensure_diag_folder()
        report(True, "Diagnostic files folder: " + config.path("diag"))
    except OSError as e:
        report(False, "Can't create diagnostic files folder: {0}".format(e))

    try:
        import epics

        report(True, "EPICS Channel Access library: {0}".format(epics.ca.find_lib("ca")))
    except Exception as e:
        report(False, "EPICS Channel Access library not found: {0}".format(e))
    return ok
