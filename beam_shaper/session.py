"""Wires the core loop to real or simulated hardware. No GUI code here."""

from beam_shaper.core.diagnostics import DiagnosticWriter
from beam_shaper.core.loop import LoopEngine, LoopParameters
from beam_shaper.core.plugins import load_awg_filter, load_correction_algorithm
from beam_shaper.core.settings import num_points


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
    correction_fn, err = load_correction_algorithm(config.algorithm)
    if err:
        warnings.append((err, "Correction algorithm error"))
    filter_fn, err = load_awg_filter(config.filter)
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

    engine = LoopEngine(
        target.get_processed(),
        LoopParameters.from_settings(config, settings),
        awg,
        feedback,
        correction_fn=correction_fn,
        filter_fn=filter_fn,
        diagnostics=DiagnosticWriter(config.diag) if settings.save_diag_files else None,
        background_raw=background.get_raw(),
    )
    return engine, warnings


def prepare_worker_thread(sim):
    """Call at the start of any thread that will talk to hardware."""
    if not sim:
        from beam_shaper.hardware.epics_scope import attach_to_thread

        attach_to_thread()
