from dash import Input, Output, State, callback_context
import plotly.graph_objects as go
from utils.interactions import handle_selection
from utils.interactions import handle_hover

def register_hover_selection_callbacks(app, df, fig_map):
    @app.callback(
        [Output('route-map', 'figure'),
         Output('stats-output', 'children')],
        [Input('elevation-profile', 'hoverData'),
         Input('elevation-profile', 'selectedData')],
        [State('map-zoom-store', 'data'),
         State('map-center-store', 'data')]
    )
    def update_map_on_hover_or_selection(hoverData, selectedData, current_zoom, current_center):
        triggered = callback_context.triggered[0]['prop_id']
        fig_map_copy = go.Figure(fig_map)

        if 'selectedData' in triggered and selectedData is not None:
            return handle_selection(selectedData, df, fig_map_copy, current_zoom, current_center)

        elif 'hoverData' in triggered and hoverData is not None:
            return handle_hover(hoverData, df, fig_map_copy, current_zoom, current_center), ''

        return fig_map_copy, ''

