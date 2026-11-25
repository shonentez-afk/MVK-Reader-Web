"""Pure worker-side calculation for original saved ADC/TACH timeline dragging."""
from .original_view_time_source import source_view_time
from .envelope_spectrum_idr_candidate import source_selected_envelope_fft_plan


def direct_drag_spectrum(flow, position, n, mode, code, profile, backend, domain):
    """Perform only data and numerical work; never touch the UI from here."""
    session = flow.session
    with session.sample_render_transaction():
        clock = source_view_time(flow, position=position)
        available = clock.selected_start_sample
        fs = clock.sample_rate_hz
        if flow.tach_byte and clock.position == clock.maximum:
            available = clock.sample_count
        if code:
            plan = source_selected_envelope_fft_plan(n, int(fs), code)
            if (available < plan["source_getadjusted_length_samples"]
                    or plan["post_fir_fft_n"] < 8):
                return None
            return flow.spectrum_envelope(
                code, n, profile, end_s=available/fs, mode=mode,
                backend=backend, source_selected_bspec_lines=True, **domain)
        if not flow.tach_byte and 0 < available < n:
            return session.preview_partial_spectrum(
                flow.channel, n, mode, available, **domain)
        if available < n:
            return None
        kw = {} if flow.tach_byte else domain
        return flow.spectrum(n, mode, (available-n)/fs, max_hz=1e9,
                             max_points=n//2, backend=backend, **kw)
