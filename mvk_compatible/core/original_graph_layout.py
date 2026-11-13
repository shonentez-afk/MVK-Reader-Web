"""Live plot layout contract, shared by PageAdc and PageSpectrum.

Source: Unit115 007CA593..007CA62F and mvkform pnAdcGraph/pnSpecGraph.
Inputs are measured font metrics; native GDI parity is not inferred.
"""
from .tqgrapher_canvas_idr_candidate import source_canvas_geometry

SOURCE_GRAPH_PANEL_BORDER = 8


def source_graph_layout(*, width, height, zero_width, six_decimals_width,
                        text_height, x_name=True, y_name=True):
    canvas = source_canvas_geometry(
        pixel_width=width, pixel_height=height,
        margin=min(width//53,height//30),
        zero_text_width=zero_width,
        six_decimals_text_width=six_decimals_width,
        zero_text_height=text_height,
        x_name_present=x_name, y_name_present=y_name)
    # Layout has no series/viewport input. Never expose its placeholder
    # affine coefficients as the current graph's sample transforms.
    return {
        key: canvas[key] for key in (
            'canvas_width', 'canvas_height', 'margin', 'pixel_left',
            'pixel_right', 'pixel_top', 'pixel_bottom', 'pixel_plot_width',
            'pixel_plot_height', 'x_fallback_to_margin', 'y_fallback_to_margin',
            'original_source_formula_verified', 'original_pixel_rectangle_verified',
            'original_canvas_font_metrics_verified')
    }
